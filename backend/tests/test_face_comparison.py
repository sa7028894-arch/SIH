import io
import cv2
import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

from app.main import app
from app.models.face import BoundingBox, ExtractedFace, FaceCompareResponse, FaceExtractionResponse
from app.services.face_detector import FaceDetectorService
from app.services.openface_service import OpenFaceService
from app.controllers.face_controller import FaceController
from app.core.config import settings

client = TestClient(app)


def create_dummy_image_bytes(width: int = 120, height: int = 120, color=(128, 128, 128)) -> bytes:
    """Helper to create an in-memory JPEG image buffer."""
    img = np.full((height, width, 3), color, dtype=np.uint8)
    success, encoded = cv2.imencode(".jpg", img)
    assert success
    return encoded.tobytes()


# ==========================================
# Unit Tests: FaceDetectorService
# ==========================================

def test_load_image_from_bytes_invalid():
    """Verify that corrupt or non-image bytes return None."""
    result = FaceDetectorService.load_image_from_bytes(b"not an image", "test.jpg")
    assert result is None


def test_load_image_from_bytes_valid_jpeg():
    """Verify that valid JPEG bytes are decoded into an OpenCV BGR numpy array."""
    raw_bytes = create_dummy_image_bytes(80, 80)
    img = FaceDetectorService.load_image_from_bytes(raw_bytes, "sample.jpg")
    assert img is not None
    assert img.shape == (80, 80, 3)


def test_detect_face_on_solid_image():
    """Solid color image should not have any face detected."""
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    found, bbox, conf, cropped, b64 = FaceDetectorService.detect_face(img)
    assert found is False
    assert bbox is None
    assert conf == 0.0
    assert cropped is None
    assert b64 is None


def test_extract_face_from_bytes_blank():
    """extract_face_from_bytes should return ExtractedFace with face_detected=False for blank image."""
    raw_bytes = create_dummy_image_bytes(100, 100)
    face_meta, face_crop = FaceDetectorService.extract_face_from_bytes(raw_bytes, "blank.png")
    assert face_meta.face_detected is False
    assert face_meta.confidence == 0.0
    assert face_crop is None


# ==========================================
# Unit Tests: OpenFaceService
# ==========================================

def test_openface_preprocess():
    """Test image resizing to 96x96 blob and normalization to [0, 1] range."""
    raw = np.full((200, 150, 3), 255, dtype=np.uint8)
    blob = OpenFaceService._preprocess_face(raw)
    assert blob.shape == (1, 3, 96, 96)
    assert blob.dtype == np.float32
    assert np.allclose(blob, 1.0, atol=1e-3)


def test_openface_compare_identical_faces():
    """Comparing an image to itself must yield distance 0.0, similarity 100.0%, and is_match=True."""
    dummy_face = np.random.randint(0, 256, (96, 96, 3), dtype=np.uint8)
    is_match, sim, dist = OpenFaceService.compare_faces(dummy_face, dummy_face)

    assert is_match is True
    assert dist == pytest.approx(0.0, abs=1e-4)
    assert sim == pytest.approx(100.0, abs=0.1)


def test_openface_compare_different_faces():
    """Comparing different images should produce positive distance and proper similarity score."""
    face1 = np.zeros((96, 96, 3), dtype=np.uint8)
    face2 = np.full((96, 96, 3), 255, dtype=np.uint8)
    is_match, sim, dist = OpenFaceService.compare_faces(face1, face2)

    assert dist > 0.0
    assert 0.0 <= sim <= 100.0
    assert isinstance(is_match, bool)


def test_openface_compute_embedding():
    """compute_embedding should return a normalized 128-dimensional vector."""
    dummy = np.full((96, 96, 3), 100, dtype=np.uint8)
    emb = OpenFaceService.compute_embedding(dummy)
    assert emb is not None
    assert emb.shape == (128,)
    # Embedding must be L2 normalized (norm close to 1.0)
    norm = np.linalg.norm(emb)
    assert norm == pytest.approx(1.0, abs=1e-3)


# ==========================================
# Integration Tests: Controller & Endpoints
# ==========================================

def test_extract_face_endpoint_unsupported_type():
    """Reject unsupported file extensions (e.g. .txt)."""
    response = client.post(
        "/api/v1/extract-face",
        files={"file": ("test.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_extract_face_endpoint_blank_image():
    """Valid image with no face should return success=True but face_detected=False."""
    img_bytes = create_dummy_image_bytes(100, 100)
    response = client.post(
        "/api/v1/extract-face",
        files={"file": ("blank.jpg", img_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["face_detected"] is False
    assert data["face"] is None


def test_face_compare_endpoint_unsupported_file():
    """Reject invalid file extensions in face-compare."""
    img_bytes = create_dummy_image_bytes(100, 100)
    response = client.post(
        "/api/v1/face-compare",
        files={
            "document_file": ("test.txt", b"invalid", "text/plain"),
            "live_file": ("live.jpg", img_bytes, "image/jpeg"),
        },
    )
    assert response.status_code == 400


def test_face_compare_endpoint_no_face_detected():
    """When both files contain blank images, endpoint returns is_match=False and descriptive message."""
    img_bytes = create_dummy_image_bytes(100, 100)
    response = client.post(
        "/api/v1/face-compare",
        files={
            "document_file": ("doc.jpg", img_bytes, "image/jpeg"),
            "live_file": ("live.jpg", img_bytes, "image/jpeg"),
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["is_match"] is False
    assert "reference document" in data["message"].lower()


def test_face_compare_endpoint_successful_match():
    """Mocking face extraction to return synthetic face crops verifies full matching flow."""
    synthetic_face = np.full((112, 112, 3), 150, dtype=np.uint8)

    mock_doc_extracted = (
        ExtractedFace(
            face_detected=True,
            image_base64="data:image/jpeg;base64,mockdoc",
            bbox=BoundingBox(x=10, y=10, width=50, height=50),
            confidence=0.95,
        ),
        synthetic_face,
    )
    mock_live_extracted = (
        ExtractedFace(
            face_detected=True,
            image_base64="data:image/jpeg;base64,mocklive",
            bbox=BoundingBox(x=15, y=15, width=48, height=48),
            confidence=0.98,
        ),
        synthetic_face,
    )

    with patch.object(
        FaceDetectorService,
        "extract_face_from_bytes",
        side_effect=[mock_doc_extracted, mock_live_extracted],
    ):
        img_bytes = create_dummy_image_bytes(100, 100)
        response = client.post(
            "/api/v1/face-compare",
            files={
                "document_file": ("doc_pass.jpg", img_bytes, "image/jpeg"),
                "live_file": ("live_snap.jpg", img_bytes, "image/jpeg"),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_match"] is True
        assert data["similarity_score"] == pytest.approx(100.0, abs=0.5)
        assert data["distance"] == pytest.approx(0.0, abs=1e-3)
        assert data["threshold"] == settings.FACE_MATCH_THRESHOLD
        assert data["doc_face"]["face_detected"] is True
        assert data["live_face"]["face_detected"] is True
        assert "Identity verified" in data["message"]
