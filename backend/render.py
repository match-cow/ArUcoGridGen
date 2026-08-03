from __future__ import annotations

import io
import json

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas

from .models import ArucoBoard, CharucoBoard, Checkerboard
from .scene import (
    FRAME_LABEL_FONT_PT,
    FRAME_STROKE_MM,
    FRAME_UNDER_STROKE_MM,
    FrameGeometry,
    FrameLabel,
    FrameLine,
    Rect,
    Scene,
)
from .typography import ANNOTATION_FONT_PT, FONT_NAME, FONT_PATH


FRAME_COLORS = {"X": "#d32f2f", "Y": "#2e7d32", "Z": "#1565c0"}
ANNOTATION_HORIZONTAL_INSET_MM = 0.5


def _number(value: float) -> str:
    return f"{value:g}"


def annotation_text(scene: Scene, name: str) -> str:
    board = scene.request.board
    if name != "parameters":
        raise ValueError(f"Unsupported text annotation: {name}")
    if isinstance(board, ArucoBoard):
        details = (
            f"ArUco  |  {board.dictionary}  |  {board.columns}x{board.rows} markers"
            f"  |  {_number(board.marker_size_mm)} mm marker"
            f"  |  {_number(board.separation_mm)} mm separation"
        )
    elif isinstance(board, CharucoBoard):
        details = (
            f"ChArUco  |  {board.dictionary}  |  {board.squares_x}x{board.squares_y} squares"
            f"  |  {_number(board.square_size_mm)} mm square"
            f"  |  {_number(board.marker_size_mm)} mm marker"
        )
    elif isinstance(board, Checkerboard):
        details = (
            f"Checkerboard  |  {board.squares_x}x{board.squares_y} squares"
            f"  |  {_number(board.square_size_mm)} mm square"
            f"  |  {_number(board.border_mm)} mm border"
        )
    compensation = scene.request.print_compensation
    return (
        f"{details}  |  compensation {_number(compensation.x_percent)}%"
        f" x {_number(compensation.y_percent)}%"
    )


def _annotation_font_size(scene: Scene, name: str) -> float:
    """Keep metadata readable while fitting it inside narrow printable pages."""
    text_width = (
        pdfmetrics.stringWidth(annotation_text(scene, name), FONT_NAME, ANNOTATION_FONT_PT) / mm
    )
    available_width = max(
        0.1,
        scene.annotation_rects[name].width - 2 * ANNOTATION_HORIZONTAL_INSET_MM,
    )
    return min(ANNOTATION_FONT_PT, ANNOTATION_FONT_PT * available_width / text_width)


def _annotation_baseline(box: Rect, font_size_pt: float = ANNOTATION_FONT_PT) -> float:
    """Center Vera text optically and return its shared scene baseline."""
    ascent_pt, descent_pt = pdfmetrics.getAscentDescent(FONT_NAME, font_size_pt)
    ascent = ascent_pt * 25.4 / 72
    descent_depth = -descent_pt * 25.4 / 72
    return box.y + box.height / 2 + (ascent - descent_depth) / 2


def _frame_lines(frame: FrameGeometry) -> dict[str, tuple[FrameLine, ...]]:
    return {
        "X": (frame.x_axis.shaft, *frame.x_axis.arrowheads),
        "Y": (frame.y_axis.shaft, *frame.y_axis.arrowheads),
        "Z": frame.z_axis.cross,
    }


def _frame_labels(frame: FrameGeometry) -> tuple[FrameLabel, FrameLabel, FrameLabel]:
    return (frame.x_axis.label, frame.y_axis.label, frame.z_axis.label)


def render_png(scene: Scene, cap: int = 1600) -> bytes:
    scale = min(cap / scene.page.width, cap / scene.page.height)
    width, height = round(scene.page.width * scale), round(scene.page.height * scale)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    def rect(item: Rect, fill: str):
        draw.rectangle(
            (
                round(item.x * scale),
                round(item.y * scale),
                round((item.x + item.width) * scale),
                round((item.y + item.height) * scale),
            ),
            fill=fill,
        )

    for item in scene.black_rects:
        rect(item, "black")
    for item in scene.white_rects:
        rect(item, "white")
    for item in scene.marker_rects:
        rect(item, "black")
    for item in scene.marker_white_rects:
        rect(item, "white")

    def font_for(points: float):
        pixels = max(1, round(points * scale * 25.4 / 72))
        return ImageFont.truetype(str(FONT_PATH), pixels)

    for marker_id, x, y in scene.marker_labels:
        draw.text(
            (x * scale, y * scale),
            str(marker_id),
            fill="black",
            font=font_for(scene.request.board.id_font_size_pt),
            anchor="mm",
        )
    for name, box in scene.annotation_rects.items():
        if name in {"ruler", "frame_legend"}:
            continue
        font_size = _annotation_font_size(scene, name)
        draw.text(
            ((box.x + box.width / 2) * scale, _annotation_baseline(box, font_size) * scale),
            annotation_text(scene, name),
            fill="black",
            font=font_for(font_size),
            anchor="ms",
        )
    if scene.ruler:
        ruler_font = font_for(ANNOTATION_FONT_PT)
        x1, x2, y = scene.ruler.baseline
        draw.line(
            (x1 * scale, y * scale, x2 * scale, y * scale),
            fill="black",
            width=max(1, round(scale * 0.25)),
        )
        for tick in scene.ruler.ticks:
            draw.line(
                (tick.x * scale, tick.y1 * scale, tick.x * scale, tick.y2 * scale),
                fill="black",
                width=max(1, round(scale * (0.25 if tick.major else 0.18))),
            )
        for label in scene.ruler.labels:
            draw.text(
                (label.x * scale, label.baseline_y * scale),
                label.text,
                fill="black",
                font=ruler_font,
                anchor="ms",
            )
        draw.text(
            (scene.ruler.unit.x * scale, scene.ruler.unit.baseline_y * scale),
            scene.ruler.unit.text,
            fill="black",
            font=ruler_font,
            anchor="ls",
        )
    if scene.frame:
        under_width = max(1, round(FRAME_UNDER_STROKE_MM * scale))
        color_width = max(1, round(FRAME_STROKE_MM * scale))

        def line(item: FrameLine, fill: str, width: int):
            draw.line(
                (
                    item.start[0] * scale,
                    item.start[1] * scale,
                    item.end[0] * scale,
                    item.end[1] * scale,
                ),
                fill=fill,
                width=width,
            )

        for axis, lines in _frame_lines(scene.frame).items():
            for item in lines:
                line(item, "white", under_width)
            for item in lines:
                line(item, FRAME_COLORS[axis], color_width)
        cx, cy = scene.frame.z_axis.center
        radius = scene.frame.z_axis.radius
        circle_box = (
            (cx - radius) * scale,
            (cy - radius) * scale,
            (cx + radius) * scale,
            (cy + radius) * scale,
        )
        draw.ellipse(circle_box, outline="white", width=under_width)
        draw.ellipse(circle_box, outline=FRAME_COLORS["Z"], width=color_width)
        frame_font = font_for(FRAME_LABEL_FONT_PT)
        outline_width = max(1, round(FRAME_UNDER_STROKE_MM * scale / 2))
        for label in _frame_labels(scene.frame):
            draw.text(
                (label.x * scale, label.baseline_y * scale),
                label.text,
                fill=FRAME_COLORS[label.axis],
                font=frame_font,
                anchor="ls",
                stroke_width=outline_width,
                stroke_fill="white",
            )
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()


def render_pdf(scene: Scene) -> bytes:
    output = io.BytesIO()
    c = Canvas(output, pagesize=(scene.page.width * mm, scene.page.height * mm), pageCompression=1)

    def rects(items: tuple[Rect, ...], color: float):
        if not items:
            return
        c.setFillGray(color)
        path = c.beginPath()
        for item in items:
            path.rect(
                item.x * mm,
                (scene.page.height - item.y - item.height) * mm,
                item.width * mm,
                item.height * mm,
            )
        c.drawPath(path, stroke=0, fill=1)

    rects(scene.black_rects, 0)
    rects(scene.white_rects, 1)
    rects(scene.marker_rects, 0)
    rects(scene.marker_white_rects, 1)
    c.setFillGray(0)
    for marker_id, x, y in scene.marker_labels:
        c.setFont(FONT_NAME, scene.request.board.id_font_size_pt)
        c.drawCentredString(x * mm, (scene.page.height - y) * mm, str(marker_id))
    for name, box in scene.annotation_rects.items():
        if name in {"ruler", "frame_legend"}:
            continue
        font_size = _annotation_font_size(scene, name)
        c.setFont(FONT_NAME, font_size)
        c.drawCentredString(
            (box.x + box.width / 2) * mm,
            (scene.page.height - _annotation_baseline(box, font_size)) * mm,
            annotation_text(scene, name),
        )
    if scene.ruler:
        c.setFont(FONT_NAME, ANNOTATION_FONT_PT)
        x1, x2, y = scene.ruler.baseline
        c.setLineWidth(0.25 * mm)
        c.line(x1 * mm, (scene.page.height - y) * mm, x2 * mm, (scene.page.height - y) * mm)
        for tick in scene.ruler.ticks:
            c.setLineWidth((0.25 if tick.major else 0.18) * mm)
            c.line(
                tick.x * mm,
                (scene.page.height - tick.y1) * mm,
                tick.x * mm,
                (scene.page.height - tick.y2) * mm,
            )
        for label in scene.ruler.labels:
            c.drawCentredString(
                label.x * mm, (scene.page.height - label.baseline_y) * mm, label.text
            )
        c.drawString(
            scene.ruler.unit.x * mm,
            (scene.page.height - scene.ruler.unit.baseline_y) * mm,
            scene.ruler.unit.text,
        )
    if scene.frame:
        c.saveState()
        c.setLineCap(1)
        c.setLineJoin(1)

        def line(item: FrameLine):
            c.line(
                item.start[0] * mm,
                (scene.page.height - item.start[1]) * mm,
                item.end[0] * mm,
                (scene.page.height - item.end[1]) * mm,
            )

        for axis, lines in _frame_lines(scene.frame).items():
            c.setStrokeColor(white)
            c.setLineWidth(FRAME_UNDER_STROKE_MM * mm)
            for item in lines:
                line(item)
            c.setStrokeColor(HexColor(FRAME_COLORS[axis]))
            c.setLineWidth(FRAME_STROKE_MM * mm)
            for item in lines:
                line(item)
        cx, cy = scene.frame.z_axis.center
        radius = scene.frame.z_axis.radius
        c.setFillColor(white)
        c.setStrokeColor(white)
        c.setLineWidth(FRAME_UNDER_STROKE_MM * mm)
        c.circle(cx * mm, (scene.page.height - cy) * mm, radius * mm, stroke=1, fill=0)
        c.setStrokeColor(HexColor(FRAME_COLORS["Z"]))
        c.setLineWidth(FRAME_STROKE_MM * mm)
        c.circle(cx * mm, (scene.page.height - cy) * mm, radius * mm, stroke=1, fill=0)
        for label in _frame_labels(scene.frame):
            text = c.beginText(label.x * mm, (scene.page.height - label.baseline_y) * mm)
            text.setFont(FONT_NAME, FRAME_LABEL_FONT_PT)
            text.setTextRenderMode(1)
            c.setStrokeColor(white)
            c.setLineWidth(FRAME_UNDER_STROKE_MM * mm)
            text.textOut(label.text)
            c.drawText(text)
            c.setFillColor(HexColor(FRAME_COLORS[label.axis]))
            c.setFont(FONT_NAME, FRAME_LABEL_FONT_PT)
            c.drawString(
                label.x * mm,
                (scene.page.height - label.baseline_y) * mm,
                label.text,
            )
        c.restoreState()
    c.showPage()
    c.save()
    return output.getvalue()


def manifest(scene: Scene, config_hash: str) -> bytes:
    payload = {
        "schema_version": "2.0",
        "configuration_hash": config_hash,
        "request": scene.request.model_dump(mode="json"),
        "page_bounds": scene.page.dict(),
        "target_bounds": scene.target.dict(),
        "page_placement": {"horizontal": "center", "vertical": "center"},
        "annotations": {key: value.dict() for key, value in sorted(scene.annotation_rects.items())},
        "features": list(scene.features),
        "frame_convention": {
            "origin": "compensated outer board top-left",
            "x": "right",
            "y": "down",
            "z": "into page",
            "units": "millimetres",
        },
    }
    if scene.transform:
        payload["board_to_base"] = scene.transform
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()
