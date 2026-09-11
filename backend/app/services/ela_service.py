import base64
import logging
import os
from typing import Optional, Tuple

import cv2
import numpy as np

from app.core.config import settings
from app.models.ela import ElaAnalysisResponse
from app.models.face import BoundingBox
from app.services.face_detector import FaceDetectorService

logger = logging.getLogger(__name__)

JPEG_EXTENSIONS = {".jpg", ".jpeg"}
_EPS = 1e-6
_PHOTO_DILATE = 0.40
_MRZ_BAND_FRAC = 0.25


class ElaService:
    @classmethod
    def generate_heatmap(
        cls,
        image_bgr: np.ndarray,
        quality: Optional[int] = None,
        brightness: Optional[float] = None,
    ) -> np.ndarray:
        jpeg_quality = quality if quality is not None else settings.ELA_JPEG_QUALITY
        multiplier = brightness if brightness is not None else settings.ELA_BRIGHTNESS

        ok, encoded = cv2.imencode(
            ".jpg",
            image_bgr,
            [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)],
        )
        if not ok:
            raise RuntimeError("Failed to re-encode image as JPEG for ELA.")

        resaved = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if resaved is None:
            raise RuntimeError("Failed to decode re-saved JPEG for ELA.")

        if resaved.shape[:2] != image_bgr.shape[:2]:
            resaved = cv2.resize(resaved, (image_bgr.shape[1], image_bgr.shape[0]))

        delta = cv2.absdiff(image_bgr, resaved)
        ela = delta.astype(np.float32) * float(multiplier)
        return np.clip(ela, 0, 255).astype(np.uint8)

    @classmethod
    def dilate_bbox(
        cls,
        bbox: BoundingBox,
        img_w: int,
        img_h: int,
        factor: float = _PHOTO_DILATE,
    ) -> BoundingBox:
        pad_x = int(bbox.width * factor)
        pad_y = int(bbox.height * factor)
        x1 = max(0, bbox.x - pad_x)
        y1 = max(0, bbox.y - pad_y)
        x2 = min(img_w, bbox.x + bbox.width + pad_x)
        y2 = min(img_h, bbox.y + bbox.height + pad_y)
        return BoundingBox(x=x1, y=y1, width=max(1, x2 - x1), height=max(1, y2 - y1))

    @classmethod
    def _boxes_overlap(cls, a: BoundingBox, b: BoundingBox) -> bool:
        return not (
            a.x + a.width <= b.x
            or b.x + b.width <= a.x
            or a.y + a.height <= b.y
            or b.y + b.height <= a.y
        )

    @classmethod
    def background_roi(cls, photo_bbox: BoundingBox, img_w: int, img_h: int) -> BoundingBox:
        pad = max(4, int(min(img_w, img_h) * 0.02))
        right_space = img_w - (photo_bbox.x + photo_bbox.width)
        left_space = photo_bbox.x

        # Prefer the document body directly adjacent to the photo (same height)
        if right_space >= int(photo_bbox.width * 0.7):
            return BoundingBox(
                x=photo_bbox.x + photo_bbox.width + pad,
                y=photo_bbox.y,
                width=max(1, right_space - pad * 2),
                height=photo_bbox.height,
            )
        elif left_space >= int(photo_bbox.width * 0.7):
            return BoundingBox(
                x=pad,
                y=photo_bbox.y,
                width=max(1, left_space - pad * 2),
                height=photo_bbox.height,
            )

        # Fallback to bottom band if no overlap, or largest remaining quadrant
        band_h = max(1, int(img_h * _MRZ_BAND_FRAC))
        mrz = BoundingBox(x=0, y=max(0, img_h - band_h), width=img_w, height=band_h)
        if not cls._boxes_overlap(photo_bbox, mrz):
            return mrz

        remaining = []
        if photo_bbox.x > 8:
            remaining.append(BoundingBox(x=0, y=0, width=photo_bbox.x, height=img_h))
        right_x = photo_bbox.x + photo_bbox.width
        if img_w - right_x > 8:
            remaining.append(BoundingBox(x=right_x, y=0, width=img_w - right_x, height=img_h))
        if photo_bbox.y > 8:
            remaining.append(BoundingBox(x=0, y=0, width=img_w, height=photo_bbox.y))
        below_y = photo_bbox.y + photo_bbox.height
        if img_h - below_y > 8:
            remaining.append(BoundingBox(x=0, y=below_y, width=img_w, height=img_h - below_y))

        if remaining:
            return max(remaining, key=lambda b: b.width * b.height)

        return BoundingBox(x=0, y=0, width=img_w, height=img_h)

    @classmethod
    def roi_mean(cls, gray: np.ndarray, bbox: BoundingBox) -> float:
        h, w = gray.shape[:2]
        x1 = max(0, min(w, bbox.x))
        y1 = max(0, min(h, bbox.y))
        x2 = max(x1 + 1, min(w, bbox.x + bbox.width))
        y2 = max(y1 + 1, min(h, bbox.y + bbox.height))
        crop = gray[y1:y2, x1:x2]
        if crop.size == 0:
            return 0.0
        return float(np.mean(crop))

    @classmethod
    def encode_jpeg_data_url(cls, image_bgr: np.ndarray, quality: int = 90) -> Optional[str]:
        ok, buf = cv2.imencode(".jpg", image_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if not ok:
            return None
        b64 = base64.b64encode(buf).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"

    @classmethod
    def _draw_overlay(
        cls,
        original: np.ndarray,
        photo_bbox: Optional[BoundingBox],
        background_bbox: Optional[BoundingBox],
    ) -> np.ndarray:
        overlay = original.copy()
        if background_bbox is not None:
            cv2.rectangle(
                overlay,
                (background_bbox.x, background_bbox.y),
                (background_bbox.x + background_bbox.width, background_bbox.y + background_bbox.height),
                (255, 160, 40),
                2,
            )
        if photo_bbox is not None:
            cv2.rectangle(
                overlay,
                (photo_bbox.x, photo_bbox.y),
                (photo_bbox.x + photo_bbox.width, photo_bbox.y + photo_bbox.height),
                (80, 220, 120),
                2,
            )
        return overlay

    @classmethod
    def analyze_array(
        cls,
        image_bgr: np.ndarray,
        filename: str = "image.jpg",
        photo_bbox: Optional[BoundingBox] = None,
        background_bbox: Optional[BoundingBox] = None,
        detect_face: bool = True,
    ) -> Tuple[np.ndarray, ElaAnalysisResponse]:
        ext = os.path.splitext(filename)[1].lower()
        source_reencoded = ext not in JPEG_EXTENSIONS

        heatmap = cls.generate_heatmap(image_bgr)
        gray = cv2.cvtColor(heatmap, cv2.COLOR_BGR2GRAY)
        img_h, img_w = image_bgr.shape[:2]
        face_detected = False

        if photo_bbox is None and detect_face:
            found, face_box, _, _, _ = FaceDetectorService.detect_face(image_bgr)
            if found and face_box is not None:
                face_detected = True
                photo_bbox = cls.dilate_bbox(face_box, img_w, img_h)
        elif photo_bbox is not None:
            face_detected = True

        if photo_bbox is not None and background_bbox is None:
            background_bbox = cls.background_roi(photo_bbox, img_w, img_h)

        if photo_bbox is None:
            overall = float(np.mean(gray))
            overlay = cls._draw_overlay(image_bgr, None, None)
            response = ElaAnalysisResponse(
                success=True,
                is_suspicious=False,
                face_detected=False,
                photo_ela_mean=round(overall, 4),
                background_ela_mean=round(overall, 4),
                ratio=1.0,
                threshold=settings.ELA_RATIO_THRESHOLD,
                source_reencoded=source_reencoded,
                message=(
                    "No portrait face was found, so photo-vs-background ELA could not run. "
                    "Heatmap is shown for visual inspection only. ELA is a heuristic, not proof of forgery."
                ),
                filename=filename,
                heatmap_base64=cls.encode_jpeg_data_url(heatmap),
                overlay_base64=cls.encode_jpeg_data_url(overlay),
                photo_bbox=None,
                background_bbox=None,
            )
            return heatmap, response

        photo_mean = cls.roi_mean(gray, photo_bbox)
        bg_mean = cls.roi_mean(gray, background_bbox) if background_bbox is not None else photo_mean
        ratio = max(photo_mean, _EPS) / max(bg_mean, _EPS)
        threshold = settings.ELA_RATIO_THRESHOLD
        is_suspicious = ratio >= threshold

        if is_suspicious:
            message = (
                "Photo region compression error is significantly higher than the document background. "
                "Flag for secondary inspection. ELA is a heuristic, not proof of forgery."
            )
        else:
            message = (
                "Photo compression error is consistent with document background. "
                "ELA is a heuristic, not proof of authenticity."
            )
        if source_reencoded:
            message += " Source was not JPEG; the document was rasterized before analysis, which can weaken ELA."

        overlay = cls._draw_overlay(image_bgr, photo_bbox, background_bbox)
        response = ElaAnalysisResponse(
            success=True,
            is_suspicious=is_suspicious,
            face_detected=face_detected,
            photo_ela_mean=round(photo_mean, 4),
            background_ela_mean=round(bg_mean, 4),
            ratio=round(ratio, 4),
            threshold=threshold,
            source_reencoded=source_reencoded,
            message=message,
            filename=filename,
            heatmap_base64=cls.encode_jpeg_data_url(heatmap),
            overlay_base64=cls.encode_jpeg_data_url(overlay),
            photo_bbox=photo_bbox,
            background_bbox=background_bbox,
        )
        return heatmap, response

    @classmethod
    def analyze_bytes(cls, file_bytes: bytes, filename: str) -> ElaAnalysisResponse:
        image_bgr = FaceDetectorService.load_image_from_bytes(file_bytes, filename)
        if image_bgr is None:
            raise ValueError(f"Could not decode media '{filename}'.")
        _, response = cls.analyze_array(image_bgr, filename=filename)
        return response
