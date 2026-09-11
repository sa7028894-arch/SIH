import io
import cv2
import numpy as np
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.models.face import BoundingBox
from app.services.ela_service import ElaService

client = TestClient(app)


def _jpeg_bytes(img: np.ndarray, quality: int) -> bytes:
    ok, encoded = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    assert ok
    return encoded.tobytes()


def _from_jpeg(img: np.ndarray, quality: int) -> np.ndarray:
    decoded = cv2.imdecode(np.frombuffer(_jpeg_bytes(img, quality), np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None
    return decoded


def test_uniform_jpeg_ratio_near_one():
    rng = np.random.default_rng(5)
    canvas = np.full((240, 320, 3), 140, dtype=np.uint8)
    noise = rng.integers(0, 18, canvas.shape, dtype=np.uint8)
    canvas = cv2.add(canvas, noise)
    original = _from_jpeg(canvas, 90)

    photo = BoundingBox(x=20, y=20, width=80, height=80)
    background = BoundingBox(x=160, y=40, width=120, height=80)
    _, result = ElaService.analyze_array(
        original,
        filename="uniform.jpg",
        photo_bbox=photo,
        background_bbox=background,
        detect_face=False,
    )

    assert result.success is True
    assert result.face_detected is True
    assert result.source_reencoded is False
    assert result.ratio == pytest.approx(1.0, rel=0.35)
    assert result.is_suspicious is False


def test_spliced_compression_flags_suspicious():
    rng = np.random.default_rng(42)
    background = np.full((280, 360, 3), 118, dtype=np.uint8)
    background += rng.integers(0, 12, background.shape, dtype=np.uint8)
    background = _from_jpeg(background, 90)

    patch = rng.integers(0, 255, (90, 90, 3), dtype=np.uint8)
    patch = _from_jpeg(patch, 30)

    composite = background.copy()
    x, y, w, h = 24, 24, 90, 90
    composite[y : y + h, x : x + w] = patch

    photo = BoundingBox(x=x, y=y, width=w, height=h)
    background_box = BoundingBox(x=160, y=40, width=160, height=180)
    _, result = ElaService.analyze_array(
        composite,
        filename="spliced.jpg",
        photo_bbox=photo,
        background_bbox=background_box,
        detect_face=False,
    )

    assert result.success is True
    assert result.photo_ela_mean > result.background_ela_mean
    assert result.is_suspicious is True
    assert result.ratio >= result.threshold


def test_missing_face_not_flagged():
    blank = np.full((160, 160, 3), 90, dtype=np.uint8)
    original = _from_jpeg(blank, 90)
    _, result = ElaService.analyze_array(original, filename="blank.jpg", detect_face=True)

    assert result.success is True
    assert result.face_detected is False
    assert result.is_suspicious is False
    assert result.photo_bbox is None
    assert result.heatmap_base64 is not None


def test_png_source_marked_reencoded():
    png = np.full((80, 80, 3), 200, dtype=np.uint8)
    photo = BoundingBox(x=8, y=8, width=24, height=24)
    bg = BoundingBox(x=40, y=8, width=24, height=24)
    _, result = ElaService.analyze_array(
        png,
        filename="scan.png",
        photo_bbox=photo,
        background_bbox=bg,
        detect_face=False,
    )
    assert result.source_reencoded is True


def test_ela_endpoint_empty_file():
    response = client.post(
        "/api/v1/ela-analysis",
        files={"file": ("empty.jpg", io.BytesIO(b""), "image/jpeg")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_ela_endpoint_unsupported_format():
    response = client.post(
        "/api/v1/ela-analysis",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400


def test_ela_endpoint_invalid_bytes():
    response = client.post(
        "/api/v1/ela-analysis",
        files={"file": ("bad.jpg", io.BytesIO(b"not-an-image"), "image/jpeg")},
    )
    assert response.status_code == 400
