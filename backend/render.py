from __future__ import annotations

import io
import json

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas

from .models import ArucoBoard, CharucoBoard, Checkerboard
from .scene import Rect, Scene
from .typography import ANNOTATION_FONT_PT, FONT_NAME, FONT_PATH


def _number(value: float) -> str:
    return f"{value:g}"


def annotation_text(scene: Scene, name: str) -> str:
    board = scene.request.board
    if name == "frame_legend":
        return "Board frame: +X right  |  +Y down  |  +Z into page"
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


def _annotation_baseline(box: Rect) -> float:
    """Center Vera text optically and return its shared scene baseline."""
    ascent_pt, descent_pt = pdfmetrics.getAscentDescent(FONT_NAME, ANNOTATION_FONT_PT)
    ascent = ascent_pt * 25.4 / 72
    descent_depth = -descent_pt * 25.4 / 72
    return box.y + box.height / 2 + (ascent - descent_depth) / 2


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
        if name == "ruler":
            continue
        draw.text(
            ((box.x + box.width / 2) * scale, _annotation_baseline(box) * scale),
            annotation_text(scene, name),
            fill="black",
            font=font_for(ANNOTATION_FONT_PT),
            anchor="ms",
        )
    if scene.ruler:
        ruler_font = font_for(ANNOTATION_FONT_PT)
        x1, x2, y = scene.ruler.baseline
        draw.line((x1 * scale, y * scale, x2 * scale, y * scale), fill="black", width=max(1, round(scale * 0.25)))
        for tick in scene.ruler.ticks:
            draw.line((tick.x * scale, tick.y1 * scale, tick.x * scale, tick.y2 * scale), fill="black", width=max(1, round(scale * (0.25 if tick.major else 0.18))))
        for label in scene.ruler.labels:
            draw.text((label.x * scale, label.baseline_y * scale), label.text, fill="black", font=ruler_font, anchor="ms")
        draw.text((scene.ruler.unit.x * scale, scene.ruler.unit.baseline_y * scale), scene.ruler.unit.text, fill="black", font=ruler_font, anchor="ls")
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
    c.setFont(FONT_NAME, ANNOTATION_FONT_PT)
    for name, box in scene.annotation_rects.items():
        if name == "ruler":
            continue
        c.drawCentredString(
            (box.x + box.width / 2) * mm,
            (scene.page.height - _annotation_baseline(box)) * mm,
            annotation_text(scene, name),
        )
    if scene.ruler:
        x1, x2, y = scene.ruler.baseline
        c.setLineWidth(0.25 * mm)
        c.line(x1 * mm, (scene.page.height - y) * mm, x2 * mm, (scene.page.height - y) * mm)
        for tick in scene.ruler.ticks:
            c.setLineWidth((0.25 if tick.major else 0.18) * mm)
            c.line(tick.x * mm, (scene.page.height - tick.y1) * mm, tick.x * mm, (scene.page.height - tick.y2) * mm)
        for label in scene.ruler.labels:
            c.drawCentredString(label.x * mm, (scene.page.height - label.baseline_y) * mm, label.text)
        c.drawString(scene.ruler.unit.x * mm, (scene.page.height - scene.ruler.unit.baseline_y) * mm, scene.ruler.unit.text)
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
