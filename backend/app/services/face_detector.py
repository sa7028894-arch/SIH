import base64
import io
import logging
import os
from pathlib import Path
from typing import Optional, Tuple
import cv2
import httpx
import numpy as np
from PIL import Image
import pypdfium2

from app.core.config import settings
from app.models.face import BoundingBox, ExtractedFace

logger = logging.getLogger(__name__)

YUNET_MODEL_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
YUNET_MODEL_NAME = "face_detection_yunet_2023mar.onnx"


class FaceDetectorService:
    """
    Service responsible for detecting and cropping cardholder/portrait faces
    from identity documents (PDFs and Images) and live camera selfies.
    Uses OpenCV YuNet DNN for sub-10ms, high-accuracy face detection.
    """

    _detector = None
    _model_path = None

    @classmethod
    def get_weights_path(cls) -> Path:
        weights_dir = Path(settings.WEIGHTS_DIR)
        weights_dir.mkdir(parents=True, exist_ok=True)
        return weights_dir / YUNET_MODEL_NAME

    @classmethod
    def ensure_model(cls) -> str:
        """Downloads the YuNet ONNX model (~230KB) if not already present."""
        model_path = cls.get_weights_path()
        if not model_path.exists() or model_path.stat().st_size < 10000:
            logger.info(f"Downloading YuNet face detection model from {YUNET_MODEL_URL}...")
            try:
                with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                    resp = client.get(YUNET_MODEL_URL)
                    resp.raise_for_status()
                    model_path.write_bytes(resp.content)
                logger.info(f"YuNet model downloaded successfully to {model_path} ({model_path.stat().st_size} bytes)")
            except Exception as e:
                logger.error(f"Failed to download YuNet model: {e}")
                raise RuntimeError(f"Could not download YuNet face detection model: {e}")
        return str(model_path)

    @classmethod
    def get_detector(cls, width: int = 320, height: int = 320):
        model_path_str = cls.ensure_model()
        # Initialize detector if not already initialized
        if cls._detector is None or cls._model_path != model_path_str:
            cls._detector = cv2.FaceDetectorYN.create(
                model=model_path_str,
                config="",
                input_size=(width, height),
                score_threshold=0.5,
                nms_threshold=0.3,
                top_k=5000,
            )
            cls._model_path = model_path_str
        return cls._detector

    @classmethod
    def load_image_from_bytes(cls, file_bytes: bytes, filename: str) -> Optional[np.ndarray]:
        """
        Converts uploaded media bytes (PDF, JPG, PNG, WEBP, etc.) into an OpenCV BGR numpy array.
        """
        ext = os.path.splitext(filename)[1].lower()

        # Handle PDF documents: render first page to image
        if ext == ".pdf":
            try:
                pdf = pypdfium2.PdfDocument(io.BytesIO(file_bytes))
                if len(pdf) == 0:
                    return None
                page = pdf[0]
                # Render page at high resolution (150 DPI)
                pil_image = page.render(scale=150 / 72.0).to_pil().convert("RGB")
                return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            except Exception as e:
                logger.error(f"Error rendering PDF '{filename}': {e}")
                return None

        # Handle raster images
        try:
            nparr = np.frombuffer(file_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                return img

            # Fallback to PIL decode for non-standard image encodings (e.g. WebP)
            pil_image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
            return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        except Exception as e:
            logger.error(f"Error decoding image '{filename}': {e}")
            return None

    @classmethod
    def detect_face(
        cls,
        img_bgr: np.ndarray,
        margin_percent: float = 0.18,
    ) -> Tuple[bool, Optional[BoundingBox], float, Optional[np.ndarray], Optional[str]]:
        """
        Detects primary face in BGR image, crops the face with margin padding,
        and returns: (face_detected, bbox, confidence, cropped_bgr, base64_jpeg_url).
        """
        if img_bgr is None or img_bgr.size == 0:
            return False, None, 0.0, None, None

        img_h, img_w = img_bgr.shape[:2]

        try:
            detector = cls.get_detector(img_w, img_h)
            detector.setInputSize((img_w, img_h))
            _, faces = detector.detect(img_bgr)
        except Exception as e:
            logger.error(f"YuNet detection error: {e}")
            faces = None

        if faces is None or len(faces) == 0:
            return False, None, 0.0, None, None

        # Select face with highest score or largest area
        best_face = None
        best_metric = -1.0

        for face in faces:
            x, y, w, h = face[:4]
            conf = float(face[-1])
            # Area * confidence combination
            metric = (w * h) * conf
            if metric > best_metric and w > 20 and h > 20:
                best_metric = metric
                best_face = face

        if best_face is None:
            return False, None, 0.0, None, None

        x, y, w, h = [int(v) for v in best_face[:4]]
        conf = round(float(best_face[-1]), 4)

        # Apply margin padding around face bounding box
        pad_x = int(w * margin_percent)
        pad_y = int(h * (margin_percent + 0.05)) # slightly more margin on top for hair

        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(img_w, x + w + pad_x)
        y2 = min(img_h, y + h + pad_y)

        cropped_bgr = img_bgr[y1:y2, x1:x2].copy()

        if cropped_bgr.size == 0:
            return False, None, 0.0, None, None

        # Encode cropped face to JPEG data URL
        success, buf = cv2.imencode(".jpg", cropped_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        if success:
            b64_str = base64.b64encode(buf).decode("utf-8")
            data_url = f"data:image/jpeg;base64,{b64_str}"
        else:
            data_url = None

        bbox = BoundingBox(x=x, y=y, width=w, height=h)
        return True, bbox, conf, cropped_bgr, data_url

    @classmethod
    def extract_face_from_bytes(
        cls,
        file_bytes: bytes,
        filename: str,
    ) -> Tuple[ExtractedFace, Optional[np.ndarray]]:
        """
        Convenience method to process media bytes and return structured ExtractedFace
        plus cropped BGR image for feature extraction.
        """
        img_bgr = cls.load_image_from_bytes(file_bytes, filename)
        if img_bgr is None:
            return ExtractedFace(face_detected=False, confidence=0.0), None

        found, bbox, conf, cropped_bgr, data_url = cls.detect_face(img_bgr)

        if not found or cropped_bgr is None:
            return ExtractedFace(face_detected=False, confidence=0.0), None

        return (
            ExtractedFace(
                face_detected=True,
                image_base64=data_url,
                bbox=bbox,
                confidence=conf,
            ),
            cropped_bgr,
        )
