import logging
import os
from pathlib import Path
from typing import Optional, Tuple
import cv2
import httpx
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

OPENFACE_MODEL_URL = "https://raw.githubusercontent.com/aakashjhawar/face-recognition-using-deep-learning/master/openface_nn4.small2.v1.t7"
OPENFACE_MODEL_NAME = "openface_nn4.small2.v1.t7"


class OpenFaceService:
    """
    Service wrapping the OpenFace deep neural network (nn4.small2.v1)
    via OpenCV DNN for computing 128-dimensional facial embeddings
    and calculating Euclidean distance and percentage similarity.
    """

    _net_instance = None
    _model_path_cached = None

    @classmethod
    def get_weights_path(cls) -> Path:
        weights_dir = Path(settings.WEIGHTS_DIR)
        weights_dir.mkdir(parents=True, exist_ok=True)
        return weights_dir / (settings.OPENFACE_MODEL_NAME or OPENFACE_MODEL_NAME)

    @classmethod
    def ensure_model(cls) -> str:
        """
        Ensures the OpenFace Torch7 pre-trained model (.t7) exists locally.
        Downloads it if missing.
        """
        model_path = cls.get_weights_path()
        if not model_path.exists() or model_path.stat().st_size < 30000000:
            logger.info(f"Downloading OpenFace pre-trained model from {OPENFACE_MODEL_URL}...")
            try:
                with httpx.Client(timeout=120.0, follow_redirects=True) as client:
                    resp = client.get(OPENFACE_MODEL_URL)
                    resp.raise_for_status()
                    model_path.write_bytes(resp.content)
                logger.info(f"OpenFace model downloaded successfully: {model_path} ({model_path.stat().st_size} bytes)")
            except Exception as e:
                logger.error(f"Failed to download OpenFace weights: {e}")
                if model_path.exists():
                    model_path.unlink()
                raise RuntimeError(f"Could not initialize OpenFace weights: {e}")
        return str(model_path)

    @classmethod
    def get_net(cls):
        """
        Initializes and returns the OpenCV DNN Net instance for OpenFace.
        """
        model_path_str = cls.ensure_model()
        if cls._net_instance is None or cls._model_path_cached != model_path_str:
            try:
                cls._net_instance = cv2.dnn.readNetFromTorch(model_path_str)
                cls._model_path_cached = model_path_str
                logger.info("OpenFace DNN model initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize OpenFace model: {e}")
                raise
        return cls._net_instance

    @classmethod
    def _preprocess_face(cls, face_bgr: np.ndarray) -> np.ndarray:
        """
        Preprocesses a face crop for OpenFace:
        Resizes to 96x96, converts BGR to RGB, scales pixel values by 1/255.0,
        and constructs a 4D blob (1, 3, 96, 96).
        """
        return cv2.dnn.blobFromImage(
            face_bgr,
            scalefactor=1.0 / 255.0,
            size=(96, 96),
            mean=(0, 0, 0),
            swapRB=True,
            crop=False,
        )

    @classmethod
    def compute_embedding(cls, face_bgr: np.ndarray) -> np.ndarray:
        """
        Computes an L2-normalized 128-dimensional embedding for a cropped BGR face image.
        """
        net = cls.get_net()
        blob = cls._preprocess_face(face_bgr)
        net.setInput(blob)
        output = net.forward()

        emb = output[0].flatten()
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
        Compares two cropped face images using OpenFace.
        Returns:
            - is_match (bool): Whether faces belong to the same person based on threshold.
            - similarity_score (float): Percentage similarity (0.0% to 100.0%).
            - distance (float): Euclidean L2 distance between embeddings.
        """
        emb1 = cls.compute_embedding(face1_bgr)
        emb2 = cls.compute_embedding(face2_bgr)

        raw_dist = float(np.linalg.norm(emb1 - emb2))
        distance = round(raw_dist, 4)

        # For unit-normalized vectors: Euclidean distance ranges [0.0, 2.0]
        # Cosine similarity: cos(theta) = 1.0 - (raw_dist^2) / 2.0
        cos_sim = 1.0 - ((raw_dist ** 2) / 2.0)
        sim_percentage = max(0.0, min(100.0, cos_sim * 100.0))
        similarity_score = round(sim_percentage, 2)

        match_threshold = threshold if threshold is not None else settings.FACE_MATCH_THRESHOLD
        is_match = raw_dist <= match_threshold

        return is_match, similarity_score, distance
