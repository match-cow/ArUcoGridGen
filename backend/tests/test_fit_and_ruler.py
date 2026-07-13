import asyncio

import httpx
import pytest
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics

from backend.fit import fit_request
from backend.app import app
from backend.errors import FitError
from backend.models import GenerateRequest
from backend.render import annotation_text, render_pdf, render_png
from backend.scene import build_scene
from backend.typography import ANNOTATION_FONT_PT, FONT_NAME


def body(board, orientation="portrait", paper="A4"):
    payload = GenerateRequest().model_dump(mode="json")
    payload["page"] = {"paper_size": paper, "orientation": orientation}
    payload["board"] = board
    return GenerateRequest.model_validate(payload)


def post_fit(payload):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post("/api/v2/fit", json=payload)

    return asyncio.run(run())


@pytest.mark.parametrize(
    "board",
    [
        {
            "type": "aruco",
            "dictionary": "DICT_5X5_100",
            "rows": 7,
            "columns": 5,
            "marker_size_mm": 30,
            "separation_mm": 10,
            "show_ids": True,
            "id_font_size_pt": 8,
        },
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
            "square_size_mm": 30,
            "border_mm": 20,
        },
    ],
)
@pytest.mark.parametrize(("paper", "orientation"), [("A4", "landscape"), ("Letter", "portrait")])
def test_fit_all_board_types_prefers_clean_geometry_and_reduces_counts(
    board, paper, orientation
):
    request = body(board, orientation, paper)
    result = fit_request(request)
    assert 0 < result.scale_factor <= 1
    if result.adjusted:
        assert result.changes
    else:
        assert result.request == request
    build_scene(result.request)
    before, after = request.board.model_dump(), result.request.board.model_dump()
    adjustable = {
        "rows",
        "columns",
        "squares_x",
        "squares_y",
        "marker_size_mm",
        "separation_mm",
        "square_size_mm",
        "border_mm",
    }
    for key in before.keys() - adjustable:
        assert after[key] == before[key]
    for key in {"rows", "columns", "squares_x", "squares_y"} & before.keys():
        assert after[key] <= before[key]
    for key in {"marker_size_mm", "separation_mm", "square_size_mm", "border_mm"} & before.keys():
        assert after[key] <= before[key]
        if after[key] >= 1:
            assert after[key].is_integer()
    for change in result.changes:
        assert change.after * 10 == int(change.after * 10)


def test_fit_keeps_valid_request_unchanged_and_accounts_for_compensation():
    request = GenerateRequest()
    result = fit_request(request)
    assert not result.adjusted and result.scale_factor == 1 and result.request == request
    payload = request.model_dump(mode="json")
    payload["print_compensation"] = {"x_percent": 120, "y_percent": 120}
    compensated = fit_request(GenerateRequest.model_validate(payload))
    assert compensated.adjusted
    assert compensated.request.print_compensation == GenerateRequest.model_validate(payload).print_compensation
    assert compensated.request.board.marker_size_mm == 30
    assert compensated.request.board.separation_mm == 10
    assert compensated.request.board.rows < request.board.rows


def test_fit_reduces_counts_when_id_label_safety_prevents_geometry_scaling():
    payload = GenerateRequest().model_dump(mode="json")
    payload["board"].update({"rows": 25, "columns": 4, "dictionary": "DICT_5X5_100"})
    result = fit_request(GenerateRequest.model_validate(payload))
    assert result.adjusted
    assert result.request.board.rows < 25
    assert result.request.board.marker_size_mm == 30
    assert result.request.board.separation_mm == 10
    build_scene(result.request)


def test_fit_replaces_fractional_geometry_with_clean_millimetres_before_reducing_grid():
    payload = GenerateRequest().model_dump(mode="json")
    payload["page"]["orientation"] = "landscape"
    payload["board"].update(
        {
            "rows": 12,
            "columns": 8,
            "marker_size_mm": 20.7,
            "separation_mm": 10.7,
        }
    )
    result = fit_request(GenerateRequest.model_validate(payload))
    assert result.adjusted
    assert result.request.board.marker_size_mm == 20
    assert result.request.board.separation_mm == 10
    assert result.request.board.rows < 12 or result.request.board.columns < 8
    build_scene(result.request)


def test_fit_endpoint_has_deterministic_response_and_structured_impossible_error(monkeypatch):
    payload = GenerateRequest().model_dump(mode="json")
    payload["page"]["orientation"] = "landscape"
    response = post_fit(payload)
    assert response.status_code == 200
    assert set(response.json()) == {"request", "adjusted", "scale_factor", "changes"}
    def reject_all(_request):
        raise FitError("annotation_fit", ["annotations"], "No annotation layout is possible")

    monkeypatch.setattr("backend.fit.build_scene", reject_all)
    error = post_fit(payload)
    assert error.status_code == 422
    assert error.json()["errors"][0]["code"] == "auto_fit_impossible"


def test_ruler_labels_are_centered_on_exact_major_ticks_and_rendered_by_both_formats():
    scene = build_scene(GenerateRequest())
    ruler = scene.ruler
    assert ruler is not None
    assert ruler.baseline[1] - ruler.baseline[0] == 100
    majors = [tick for tick in ruler.ticks if tick.major]
    assert [round(tick.x - ruler.baseline[0], 6) for tick in majors] == [0, 20, 40, 60, 80, 100]
    assert [label.x for label in ruler.labels] == [tick.x for tick in majors]
    assert ruler.unit.x > ruler.labels[-1].x + ruler.labels[-1].width / 2
    assert len(render_png(scene)) > 1000
    assert render_pdf(scene).startswith(b"%PDF")


def test_aruco_markers_use_solid_backgrounds_with_white_module_overlays():
    scene = build_scene(GenerateRequest())
    assert scene.black_rects == ()
    assert len(scene.marker_rects) == 35
    assert all(marker.width == 30 and marker.height == 30 for marker in scene.marker_rects)
    assert scene.marker_white_rects
    for cell in scene.marker_white_rects:
        assert any(
            marker.x <= cell.x
            and marker.y <= cell.y
            and cell.x + cell.width <= marker.x + marker.width
            and cell.y + cell.height <= marker.y + marker.height
            for marker in scene.marker_rects
        )


def test_charuco_annotations_use_stable_top_and_bottom_rails():
    request = body(
        {
            "type": "charuco",
            "dictionary": "DICT_5X5_250",
            "squares_x": 5,
            "squares_y": 7,
            "square_size_mm": 30,
            "marker_size_mm": 18,
        }
    )
    request = request.model_copy(
        update={
            "annotations": request.annotations.model_copy(
                update={"show_ruler": True, "show_parameters": True, "show_frame_legend": True}
            )
        }
    )
    scene = build_scene(request)
    ruler = scene.annotation_rects["ruler"]
    parameters = scene.annotation_rects["parameters"]
    legend = scene.annotation_rects["frame_legend"]

    assert ruler.y == 2
    assert legend.y + legend.height == scene.page.height - 2
    assert parameters.y + parameters.height + 2 == legend.y
    assert parameters.x == legend.x
    assert parameters.width == legend.width


@pytest.mark.parametrize(
    ("board", "expected"),
    [
        (
            {
                "type": "aruco",
                "dictionary": "DICT_5X5_100",
                "rows": 7,
                "columns": 5,
                "marker_size_mm": 30,
                "separation_mm": 10,
                "show_ids": True,
                "id_font_size_pt": 8,
            },
            ("DICT_5X5_100", "5x7 markers", "30 mm marker", "10 mm separation"),
        ),
        (
            {
                "type": "charuco",
                "dictionary": "DICT_5X5_250",
                "squares_x": 5,
                "squares_y": 7,
                "square_size_mm": 30,
                "marker_size_mm": 18,
            },
            ("DICT_5X5_250", "5x7 squares", "30 mm square", "18 mm marker"),
        ),
        (
            {
                "type": "checkerboard",
                "squares_x": 5,
                "squares_y": 8,
                "square_size_mm": 20,
                "border_mm": 10,
            },
            ("5x8 squares", "20 mm square", "10 mm border"),
        ),
    ],
)
def test_parameter_annotation_contains_board_specific_marker_geometry(board, expected):
    scene = build_scene(body(board))
    text = annotation_text(scene, "parameters")
    assert all(value in text for value in expected)
    assert "compensation 100% x 100%" in text
    text_width = pdfmetrics.stringWidth(text, FONT_NAME, ANNOTATION_FONT_PT) / mm
    assert text_width <= scene.annotation_rects["parameters"].width
