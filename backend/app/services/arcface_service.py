import logging
import os
from pathlib import Path
from typing import Optional, Tuple
import cv2
import httpx
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

ARCFACE_MODEL_URL = "https://raw.githubusercontent.com/NaumanHSA/Android-Face-Recognition-MTCNN-FaceNet/master/app/src/main/assets/MobileFaceNet.tflite"
ARCFACE_MODEL_NAME = "arcface.tflite"


class ArcFaceService:
    """
    Service wrapping the 'arcface' Python package for computing facial embeddings
    and calculating distance and percentage similarity.
    """

    _arcface_instance = None
    _model_path_cached = None

    @classmethod
    def get_weights_path(cls) -> Path:
        weights_dir = Path(settings.WEIGHTS_DIR)
        weights_dir.mkdir(parents=True, exist_ok=True)
        return weights_dir / ARCFACE_MODEL_NAME

    @classmethod
    def ensure_model(cls) -> str:
        """
        Ensures the ArcFace TFLite pre-trained model exists locally.
        Downloads it if missing.
        """
        model_path = cls.get_weights_path()
        if not model_path.exists() or model_path.stat().st_size < 1000000:
            logger.info(f"Downloading ArcFace pre-trained model from {ARCFACE_MODEL_URL}...")
            try:
                with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                    resp = client.get(ARCFACE_MODEL_URL)
                    resp.raise_for_status()
                    model_path.write_bytes(resp.content)
                logger.info(f"ArcFace model downloaded successfully: {model_path} ({model_path.stat().st_size} bytes)")
            except Exception as e:
                logger.error(f"Failed to download ArcFace weights: {e}")
                if model_path.exists():
                    model_path.unlink()
                raise RuntimeError(f"Could not initialize ArcFace weights: {e}")
        return str(model_path)

    @classmethod
    def get_instance(cls):
        """
        Initializes and returns the ArcFace package instance.
        """
        model_path_str = cls.ensure_model()
        if cls._arcface_instance is None or cls._model_path_cached != model_path_str:
            try:
                from arcface import ArcFace
                cls._arcface_instance = ArcFace.ArcFace(model_path=model_path_str)
                cls._model_path_cached = model_path_str
                logger.info("ArcFace package initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize ArcFace instance: {e}")
                raise
        return cls._arcface_instance

    @classmethod
    def _preprocess_face(cls, face_bgr: np.ndarray) -> np.ndarray:
        """Resizes, converts to RGB, and normalizes to [0, 1]."""
        rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (112, 112))
        return resized.astype(np.float32) / 255.0

    @classmethod
    def compute_embedding(cls, face_bgr: np.ndarray) -> np.ndarray:
        """
        Computes an L2-normalized embedding for a cropped BGR face image.
        Handles model batch size requirements transparently.
        """
        arcface = cls.get_instance()
        prep = cls._preprocess_face(face_bgr)

        expected_batch = arcface.input_details[0]["shape"][0]
        if expected_batch == 2:
            batch = np.stack([prep, prep])
        else:
            batch = np.expand_dims(prep, 0)

        arcface.interpreter.set_tensor(arcface.input_details[0]["index"], batch)
        arcface.interpreter.invoke()
        output_data = arcface.interpreter.get_tensor(arcface.output_details[0]["index"])

        emb = output_data[0]
        norm = np.linalg.norm(emb)
        return emb / norm if norm > 0 else emb

    @classmethod
    def compare_faces(
        cls,
        face1_bgr: np.ndarray,
        face2_bgr: np.ndarray,
        threshold: Optional[float] = None,
    ) -> Tuple[bool, float, float]:
        """
        Compares two cropped face images using ArcFace.
        Returns:
            - is_match (bool): Whether faces belong to the same person based on threshold.
            - similarity_score (float): Percentage similarity (0.0% to 100.0%).
            - distance (float): Squared L2 distance between embeddings.
        """
        arcface = cls.get_instance()
        prep1 = cls._preprocess_face(face1_bgr)
        prep2 = cls._preprocess_face(face2_bgr)

        expected_batch = arcface.input_details[0]["shape"][0]
        if expected_batch == 2:
            # Optimal single-pass batch inference for both faces
            batch = np.stack([prep1, prep2])
            arcface.interpreter.set_tensor(arcface.input_details[0]["index"], batch)
            arcface.interpreter.invoke()
            out = arcface.interpreter.get_tensor(arcface.output_details[0]["index"])
            norm1 = np.linalg.norm(out[0])
            norm2 = np.linalg.norm(out[1])
            emb1 = out[0] / norm1 if norm1 > 0 else out[0]
            emb2 = out[1] / norm2 if norm2 > 0 else out[1]
        else:
            emb1 = cls.compute_embedding(face1_bgr)
            emb2 = cls.compute_embedding(face2_bgr)

        raw_dist = float(arcface.get_distance_embeddings(emb1, emb2))
        distance = round(raw_dist, 4)

        # Map distance to percentage similarity
        # For unit vectors: dist ranges [0.0, 2.0]
        cos_sim = 1.0 - (raw_dist / 2.0)
        similarity_score = round(max(0.0, min(100.0, cos_sim * 100.0)), 2)

        match_threshold = threshold if threshold is not None else settings.FACE_MATCH_THRESHOLD
        is_match = raw_dist <= match_threshold

        return is_match, similarity_score, distance
