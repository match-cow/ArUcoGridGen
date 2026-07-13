import asyncio
import io
import json

import cv2
import fitz
import httpx
import numpy as np
from pypdf import PdfReader

from backend.app import app
from backend.models import GenerateRequest
from backend.scene import build_scene


def request(method, path, **kwargs):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(run())


def default():
    return GenerateRequest().model_dump(mode="json")


def test_health_and_capabilities():
    assert request("GET", "/api/v2/health").json() == {"status": "ok"}
    result = request("GET", "/api/v2/capabilities")
    assert result.status_code == 200
    assert result.json()["defaults"]["board"]["dictionary"] == "DICT_5X5_100"


def test_preview_is_png_and_detectable():
    response = request("POST", "/api/v2/preview", json=default())
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert len(response.headers["x-configuration-hash"]) == 64
    image = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_GRAYSCALE)
    corners, ids, _ = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_100)
    ).detectMarkers(image)
    assert sorted(ids.flatten().tolist()) == list(range(35))


def test_exports_deterministic_and_pdf_size():
    body = default()
    first = request("POST", "/api/v2/exports/config", json=body)
    second = request("POST", "/api/v2/exports/config", json=body)
    assert first.content == second.content
    assert "timestamp" not in first.text.lower()
    pdf = request("POST", "/api/v2/exports/pdf", json=body)
    reader = PdfReader(io.BytesIO(pdf.content))
    page = reader.pages[0]
    assert abs(float(page.mediabox.width) * 25.4 / 72 - 210) < 0.01
    assert abs(float(page.mediabox.height) * 25.4 / 72 - 297) < 0.01
    document = fitz.open(stream=pdf.content, filetype="pdf")
    pixmap = document[0].get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csGRAY)
    image = np.frombuffer(pixmap.samples, np.uint8).reshape(pixmap.height, pixmap.width)
    _, ids, _ = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_100)
    ).detectMarkers(image)
    assert sorted(ids.flatten().tolist()) == list(range(35))


def test_strict_and_relational_errors():
    body = default()
    body["unknown"] = True
    response = request("POST", "/api/v2/preview", json=body)
    assert response.status_code == 422
    assert response.json()["errors"][0]["path"] == ["unknown"]
    body = default()
    body["board"] = {
        "type": "charuco",
        "dictionary": "DICT_5X5_250",
        "squares_x": 5,
        "squares_y": 7,
        "square_size_mm": 20,
        "marker_size_mm": 20,
    }
    response = request("POST", "/api/v2/preview", json=body)
    assert response.status_code == 422


def test_fit_capacity_and_non_finite_errors():
    body = default()
    body["board"]["rows"] = 10
    body["board"]["columns"] = 6
    body["board"]["dictionary"] = "DICT_4X4_50"
    assert (
        request("POST", "/api/v2/preview", json=body).json()["errors"][0]["code"]
        == "dictionary_capacity"
    )
    body = default()
    body["board"]["marker_size_mm"] = 200
    error = request("POST", "/api/v2/preview", json=body).json()["errors"][0]
    assert error["code"] == "page_fit" and error["required_mm"]
    body = default()
    body["board"] = {
        "type": "charuco",
        "dictionary": "DICT_4X4_50",
        "squares_x": 11,
        "squares_y": 10,
        "square_size_mm": 1,
        "marker_size_mm": 0.5,
    }
    assert (
        request("POST", "/api/v2/preview", json=body).json()["errors"][0]["code"]
        == "dictionary_capacity"
    )
    body = default()
    body["print_compensation"]["x_percent"] = float("nan")
    response = request(
        "POST",
        "/api/v2/preview",
        content=json.dumps(body),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["path"] == ["print_compensation", "x_percent"]


def test_compensation_features_and_pose():
    body = default()
    body["print_compensation"] = {"x_percent": 101, "y_percent": 99}
    body["coordinate_frame"] = {
        "enabled": True,
        "pose": {
            "translation_x_m": 1,
            "translation_y_m": 2,
            "translation_z_m": 3,
            "roll_deg": 0,
            "pitch_deg": 0,
            "yaw_deg": 90,
        },
    }
    data = request("POST", "/api/v2/exports/config", json=body).json()
    assert data["target_bounds"]["width_mm"] == 191.9
    assert data["features"][0]["corners_mm"][1][0] == 30.3
    assert data["board_to_base"]["quaternion_xyzw"] == [0.0, 0.0, 0.707106781187, 0.707106781187]


def test_all_board_scenes_have_features():
    charuco = default()
    charuco["board"] = {
        "type": "charuco",
        "dictionary": "DICT_5X5_250",
        "squares_x": 5,
        "squares_y": 7,
        "square_size_mm": 30,
        "marker_size_mm": 18,
    }
    checker = default()
    checker["board"] = {
        "type": "checkerboard",
        "squares_x": 5,
        "squares_y": 8,
        "square_size_mm": 25,
        "border_mm": 10,
    }
    features = request("POST", "/api/v2/exports/config", json=charuco).json()["features"]
    assert sum(feature["kind"] == "marker" for feature in features) == 17
    assert sum(feature["kind"] == "charuco_corner" for feature in features) == 24
    assert len(request("POST", "/api/v2/exports/config", json=checker).json()["features"]) == 28


def test_charuco_and_checkerboard_previews_are_detector_valid():
    charuco = default()
    charuco["board"] = {
        "type": "charuco",
        "dictionary": "DICT_5X5_250",
        "squares_x": 5,
        "squares_y": 7,
        "square_size_mm": 30,
        "marker_size_mm": 18,
    }
    image = cv2.imdecode(
        np.frombuffer(request("POST", "/api/v2/preview", json=charuco).content, np.uint8),
        cv2.IMREAD_GRAYSCALE,
    )
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_250)
    detector = cv2.aruco.CharucoDetector(cv2.aruco.CharucoBoard((5, 7), 30, 18, dictionary))
    corners, ids, _, marker_ids = detector.detectBoard(image)
    assert len(marker_ids) == 17
    assert sorted(ids.flatten().tolist()) == list(range(24))
    document = fitz.open(
        stream=request("POST", "/api/v2/exports/pdf", json=charuco).content,
        filetype="pdf",
    )
    pixmap = document[0].get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csGRAY)
    image = np.frombuffer(pixmap.samples, np.uint8).reshape(pixmap.height, pixmap.width)
    _, ids, _, marker_ids = detector.detectBoard(image)
    assert len(marker_ids) == 17
    assert len(ids) == 24

    checker = default()
    checker["board"] = {
        "type": "checkerboard",
        "squares_x": 5,
        "squares_y": 8,
        "square_size_mm": 20,
        "border_mm": 10,
    }
    image = cv2.imdecode(
        np.frombuffer(request("POST", "/api/v2/preview", json=checker).content, np.uint8),
        cv2.IMREAD_GRAYSCALE,
    )
    found, corners = cv2.findChessboardCorners(image, (4, 7))
    assert found and len(corners) == 28


def test_marker_labels_require_safe_separation():
    body = default()
    body["board"]["separation_mm"] = 1
    error = request("POST", "/api/v2/preview", json=body).json()["errors"][0]
    assert error["code"] == "annotation_fit"


def test_annotations_are_inside_clearance_and_do_not_intersect_target():
    for board in (
        default()["board"],
        {
            "type": "charuco",
            "dictionary": "DICT_5X5_250",
            "squares_x": 5,
            "squares_y": 7,
            "square_size_mm": 30,
            "marker_size_mm": 18,
        },
        {
            "type": "checkerboard",
            "squares_x": 5,
            "squares_y": 8,
            "square_size_mm": 29,
            "border_mm": 20,
        },
    ):
        body = default()
        body["board"] = board
        scene = build_scene(GenerateRequest.model_validate(body))
        for annotation in scene.annotation_rects.values():
            assert annotation.x >= 2 and annotation.y >= 2
            assert annotation.x + annotation.width <= scene.page.width - 2
            assert annotation.y + annotation.height <= scene.page.height - 2
            separated = (
                annotation.x + annotation.width <= scene.target.x
                or scene.target.x + scene.target.width <= annotation.x
                or annotation.y + annotation.height <= scene.target.y
                or scene.target.y + scene.target.height <= annotation.y
            )
            assert separated
