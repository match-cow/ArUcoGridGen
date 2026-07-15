from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np
from scipy.spatial.transform import Rotation
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics

from .constants import CHARUCO_DICTIONARIES, DICTIONARIES, EDGE_CLEARANCE_MM, PAPER_SIZES_MM
from .errors import FitError
from .models import ArucoBoard, CharucoBoard, Checkerboard, GenerateRequest
from .typography import ANNOTATION_FONT_PT, FONT_NAME


FRAME_AXIS_LENGTH_MM = 18.0
FRAME_ARROWHEAD_MM = 2.5
FRAME_Z_RADIUS_MM = 2.25
FRAME_LABEL_FONT_PT = 8.0
FRAME_UNDER_STROKE_MM = 1.25
FRAME_STROKE_MM = 0.55


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    def dict(self):
        return {"x_mm": self.x, "y_mm": self.y, "width_mm": self.width, "height_mm": self.height}


@dataclass(frozen=True)
class RulerTick:
    x: float
    y1: float
    y2: float
    major: bool


@dataclass(frozen=True)
class RulerLabel:
    text: str
    x: float
    baseline_y: float
    width: float


@dataclass(frozen=True)
class RulerGeometry:
    bounds: Rect
    baseline: tuple[float, float, float]
    ticks: tuple[RulerTick, ...]
    labels: tuple[RulerLabel, ...]
    unit: RulerLabel


@dataclass(frozen=True)
class FrameLine:
    start: tuple[float, float]
    end: tuple[float, float]


@dataclass(frozen=True)
class FrameLabel:
    axis: str
    text: str
    x: float
    baseline_y: float
    width: float
    ascent: float
    descent: float


@dataclass(frozen=True)
class FrameAxis:
    axis: str
    shaft: FrameLine
    arrowheads: tuple[FrameLine, FrameLine]
    label: FrameLabel

    @property
    def endpoint(self) -> tuple[float, float]:
        return self.shaft.end


@dataclass(frozen=True)
class FrameZSymbol:
    center: tuple[float, float]
    radius: float
    cross: tuple[FrameLine, FrameLine]
    label: FrameLabel


@dataclass(frozen=True)
class FrameGeometry:
    bounds: Rect
    origin: tuple[float, float]
    x_axis: FrameAxis
    y_axis: FrameAxis
    z_axis: FrameZSymbol


@dataclass(frozen=True)
class Scene:
    request: GenerateRequest
    page: Rect
    target: Rect
    black_rects: tuple[Rect, ...]
    features: tuple[dict[str, Any], ...]
    white_rects: tuple[Rect, ...] = ()
    marker_rects: tuple[Rect, ...] = ()
    marker_white_rects: tuple[Rect, ...] = ()
    marker_labels: tuple[tuple[int, float, float], ...] = ()
    annotation_rects: dict[str, Rect] = field(default_factory=dict)
    ruler: RulerGeometry | None = None
    frame: FrameGeometry | None = None
    transform: dict[str, Any] | None = None


def ruler_geometry(x: float = 0, y: float = 0) -> RulerGeometry:
    """Return physical ruler geometry in scene coordinates (millimetres)."""
    font_height = ANNOTATION_FONT_PT * 25.4 / 72
    label_widths = {
        text: pdfmetrics.stringWidth(text, FONT_NAME, ANNOTATION_FONT_PT) / mm
        for text in ("0", "20", "40", "60", "80", "100", "mm")
    }
    baseline_y = y + font_height + 1.0 + 3.0
    start = x + label_widths["0"] / 2
    unit_left = start + 100 + label_widths["100"] / 2 + 2.0
    width = unit_left + label_widths["mm"] - x
    labels = tuple(
        RulerLabel(text, start + value, y + font_height, label_widths[text])
        for value, text in zip(range(0, 101, 20), ("0", "20", "40", "60", "80", "100"), strict=True)
    )
    ticks = tuple(
        RulerTick(
            start + value,
            baseline_y,
            baseline_y - (3.0 if value % 20 == 0 else 2.0),
            value % 20 == 0,
        )
        for value in range(0, 101, 10)
    )
    return RulerGeometry(
        Rect(x, y, width, baseline_y - y + 0.2),
        (start, start + 100, baseline_y),
        ticks,
        labels,
        RulerLabel("mm", unit_left, y + font_height, label_widths["mm"]),
    )


def frame_geometry(x: float, y: float) -> FrameGeometry:
    """Return fixed physical board-frame geometry in scene coordinates."""
    ascent_pt, descent_pt = pdfmetrics.getAscentDescent(FONT_NAME, FRAME_LABEL_FONT_PT)
    ascent = ascent_pt / mm
    descent = -descent_pt / mm

    def label(axis: str, left: float, baseline_y: float) -> FrameLabel:
        width = pdfmetrics.stringWidth(axis, FONT_NAME, FRAME_LABEL_FONT_PT) / mm
        return FrameLabel(axis, axis, left, baseline_y, width, ascent, descent)

    x_end = (x + FRAME_AXIS_LENGTH_MM, y)
    y_end = (x, y + FRAME_AXIS_LENGTH_MM)
    x_axis = FrameAxis(
        "x",
        FrameLine((x, y), x_end),
        (
            FrameLine(x_end, (x_end[0] - FRAME_ARROWHEAD_MM, y - FRAME_ARROWHEAD_MM)),
            FrameLine(x_end, (x_end[0] - FRAME_ARROWHEAD_MM, y + FRAME_ARROWHEAD_MM)),
        ),
        label(
            "X",
            x_end[0] + 1.5,
            y + (ascent - descent) / 2,
        ),
    )
    y_label_width = pdfmetrics.stringWidth("Y", FONT_NAME, FRAME_LABEL_FONT_PT) / mm
    y_axis = FrameAxis(
        "y",
        FrameLine((x, y), y_end),
        (
            FrameLine(y_end, (x - FRAME_ARROWHEAD_MM, y_end[1] - FRAME_ARROWHEAD_MM)),
            FrameLine(y_end, (x + FRAME_ARROWHEAD_MM, y_end[1] - FRAME_ARROWHEAD_MM)),
        ),
        label("Y", x - y_label_width / 2, y_end[1] + 1.5 + ascent),
    )
    z_label_width = pdfmetrics.stringWidth("Z", FONT_NAME, FRAME_LABEL_FONT_PT) / mm
    z_arm = FRAME_Z_RADIUS_MM * 0.58
    z_axis = FrameZSymbol(
        (x, y),
        FRAME_Z_RADIUS_MM,
        (
            FrameLine((x - z_arm, y - z_arm), (x + z_arm, y + z_arm)),
            FrameLine((x + z_arm, y - z_arm), (x - z_arm, y + z_arm)),
        ),
        label(
            "Z",
            x - FRAME_Z_RADIUS_MM - 1.0 - z_label_width,
            y + (ascent - descent) / 2,
        ),
    )

    padding = FRAME_UNDER_STROKE_MM / 2
    lines = (
        x_axis.shaft,
        *x_axis.arrowheads,
        y_axis.shaft,
        *y_axis.arrowheads,
        *z_axis.cross,
    )
    min_x = min(point[0] for line in lines for point in (line.start, line.end)) - padding
    min_y = min(point[1] for line in lines for point in (line.start, line.end)) - padding
    max_x = max(point[0] for line in lines for point in (line.start, line.end)) + padding
    max_y = max(point[1] for line in lines for point in (line.start, line.end)) + padding
    min_x = min(min_x, x - FRAME_Z_RADIUS_MM - padding)
    min_y = min(min_y, y - FRAME_Z_RADIUS_MM - padding)
    max_x = max(max_x, x + FRAME_Z_RADIUS_MM + padding)
    max_y = max(max_y, y + FRAME_Z_RADIUS_MM + padding)
    for item in (x_axis.label, y_axis.label, z_axis.label):
        min_x = min(min_x, item.x - padding)
        min_y = min(min_y, item.baseline_y - item.ascent - padding)
        max_x = max(max_x, item.x + item.width + padding)
        max_y = max(max_y, item.baseline_y + item.descent + padding)

    return FrameGeometry(
        Rect(min_x, min_y, max_x - min_x, max_y - min_y),
        (x, y),
        x_axis,
        y_axis,
        z_axis,
    )


def _page(req: GenerateRequest) -> tuple[float, float]:
    w, h = PAPER_SIZES_MM[req.page.paper_size]
    return (w, h) if req.page.orientation == "portrait" else (h, w)


def _dictionary(name: str, *, charuco: bool = False):
    allowed = CHARUCO_DICTIONARIES if charuco else DICTIONARIES
    if name not in allowed or not hasattr(cv2.aruco, name):
        raise FitError(
            "unsupported_dictionary", ["board", "dictionary"], f"Unsupported dictionary: {name}"
        )
    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, name)), allowed[name]


def _marker_white_cells(
    dictionary, marker_id: int, x: float, y: float, width: float, height: float
) -> list[Rect]:
    modules = int(round(np.sqrt(dictionary.markerSize**2))) + 2
    image = cv2.aruco.generateImageMarker(dictionary, marker_id, modules)
    cell_w, cell_h = width / modules, height / modules
    return [
        Rect(x + c * cell_w, y + r * cell_h, cell_w, cell_h)
        for r in range(modules)
        for c in range(modules)
        if image[r, c] >= 128
    ]


def _pose(req: GenerateRequest):
    if not req.coordinate_frame.enabled:
        return None
    p = req.coordinate_frame.pose
    rotation = Rotation.from_euler("xyz", [p.roll_deg, p.pitch_deg, p.yaw_deg], degrees=True)
    matrix = np.eye(4)
    matrix[:3, :3] = rotation.as_matrix()
    matrix[:3, 3] = [p.translation_x_m, p.translation_y_m, p.translation_z_m]
    return {
        "board_to_base_matrix": [[round(float(v), 12) for v in row] for row in matrix],
        "translation_m": [p.translation_x_m, p.translation_y_m, p.translation_z_m],
        "quaternion_xyzw": [round(float(v), 12) for v in rotation.as_quat()],
        "rotation_order": "Rz(yaw) * Ry(pitch) * Rx(roll)",
    }


def build_scene(req: GenerateRequest) -> Scene:
    page_w, page_h = _page(req)
    sx, sy = req.print_compensation.x_percent / 100, req.print_compensation.y_percent / 100
    board = req.board
    black: list[Rect] = []
    white: list[Rect] = []
    marker_backgrounds: list[Rect] = []
    marker_white: list[Rect] = []
    features: list[dict[str, Any]] = []
    labels: list[tuple[int, float, float]] = []
    label_band: Rect | None = None

    if isinstance(board, ArucoBoard):
        dictionary, capacity = _dictionary(board.dictionary)
        count = board.rows * board.columns
        if count > capacity:
            raise FitError(
                "dictionary_capacity",
                ["board"],
                f"Board needs {count} markers but dictionary contains {capacity}",
            )
        marker_w, marker_h = board.marker_size_mm * sx, board.marker_size_mm * sy
        sep_w, sep_h = board.separation_mm * sx, board.separation_mm * sy
        width = board.columns * marker_w + (board.columns - 1) * sep_w
        height = board.rows * marker_h + (board.rows - 1) * sep_h
        origin_x = (page_w - width) / 2
        origin_y = (page_h - height) / 2
        label_height = board.id_font_size_pt * 25.4 / 72
        if board.show_ids and board.rows > 1 and sep_h < label_height + 1:
            raise FitError(
                "annotation_fit",
                ["board", "show_ids"],
                "Marker ID labels need more vertical separation to avoid calibration targets",
                {"height": label_height + 1},
                {"height": sep_h},
            )
        if board.show_ids:
            label_band = Rect(origin_x, origin_y + height + 1, width, label_height)
        for row in range(board.rows):
            for col in range(board.columns):
                marker_id = row * board.columns + col
                x, y = origin_x + col * (marker_w + sep_w), origin_y + row * (marker_h + sep_h)
                marker_backgrounds.append(Rect(x, y, marker_w, marker_h))
                marker_white.extend(
                    _marker_white_cells(dictionary, marker_id, x, y, marker_w, marker_h)
                )
                corners = [[0, 0], [marker_w, 0], [marker_w, marker_h], [0, marker_h]]
                features.append(
                    {
                        "id": marker_id,
                        "kind": "marker",
                        "corners_mm": [
                            [round(x - origin_x + dx, 9), round(y - origin_y + dy, 9), 0]
                            for dx, dy in corners
                        ],
                    }
                )
                if board.show_ids:
                    if board.rows == 1:
                        label_y = origin_y + height + 1 + label_height / 2
                    elif row < board.rows - 1:
                        label_y = y + marker_h + sep_h / 2
                    else:
                        label_y = origin_y + height + 1 + label_height / 2
                    labels.append((marker_id, x + marker_w / 2, label_y))
    elif isinstance(board, CharucoBoard):
        dictionary, capacity = _dictionary(board.dictionary, charuco=True)
        marker_count = board.squares_x * board.squares_y // 2
        if marker_count > capacity:
            raise FitError(
                "dictionary_capacity",
                ["board"],
                f"Board needs {marker_count} markers but dictionary contains {capacity}",
            )
        raw = cv2.aruco.CharucoBoard(
            (board.squares_x, board.squares_y),
            board.square_size_mm,
            board.marker_size_mm,
            dictionary,
        )
        ids = raw.getIds().flatten().tolist()
        if len(ids) > capacity:
            raise FitError(
                "dictionary_capacity",
                ["board"],
                f"Board needs {len(ids)} markers but dictionary contains {capacity}",
            )
        width, height = (
            board.squares_x * board.square_size_mm * sx,
            board.squares_y * board.square_size_mm * sy,
        )
        origin_x, origin_y = (page_w - width) / 2, (page_h - height) / 2
        square_w, square_h = board.square_size_mm * sx, board.square_size_mm * sy
        for row in range(board.squares_y):
            for col in range(board.squares_x):
                # OpenCV places ChArUco markers in odd-parity (white) squares.
                if (row + col) % 2 == 0:
                    black.append(
                        Rect(
                            origin_x + col * square_w, origin_y + row * square_h, square_w, square_h
                        )
                    )
        for marker_id, corners in zip(ids, raw.getObjPoints(), strict=True):
            x0, y0 = float(corners[0][0]) * sx, float(corners[0][1]) * sy
            marker_w = board.marker_size_mm * sx
            marker_h = board.marker_size_mm * sy
            mx, my = origin_x + x0, origin_y + y0
            features.append(
                {
                    "id": int(marker_id),
                    "kind": "marker",
                    "corners_mm": [
                        [round(float(point[0]) * sx, 9), round(float(point[1]) * sy, 9), 0]
                        for point in corners
                    ],
                }
            )
            # Knock out the checker square, then render one solid marker with
            # white modules. This avoids hairlines between adjacent black cells.
            white.append(Rect(mx, my, marker_w, marker_h))
            marker_backgrounds.append(Rect(mx, my, marker_w, marker_h))
            marker_white.extend(
                _marker_white_cells(dictionary, int(marker_id), mx, my, marker_w, marker_h)
            )
        for corner_id, point in enumerate(raw.getChessboardCorners()):
            features.append(
                {
                    "id": corner_id,
                    "kind": "charuco_corner",
                    "point_mm": [round(float(point[0]) * sx, 9), round(float(point[1]) * sy, 9), 0],
                }
            )
    else:
        assert isinstance(board, Checkerboard)
        inner_w, inner_h = (
            board.squares_x * board.square_size_mm * sx,
            board.squares_y * board.square_size_mm * sy,
        )
        border_w, border_h = board.border_mm * sx, board.border_mm * sy
        width, height = inner_w + 2 * border_w, inner_h + 2 * border_h
        origin_x, origin_y = (page_w - width) / 2, (page_h - height) / 2
        square_w, square_h = board.square_size_mm * sx, board.square_size_mm * sy
        for row in range(board.squares_y):
            for col in range(board.squares_x):
                if (row + col) % 2:
                    black.append(
                        Rect(
                            origin_x + border_w + col * square_w,
                            origin_y + border_h + row * square_h,
                            square_w,
                            square_h,
                        )
                    )
        i = 0
        for row in range(1, board.squares_y):
            for col in range(1, board.squares_x):
                features.append(
                    {
                        "id": i,
                        "kind": "checker_corner",
                        "point_mm": [
                            round(border_w + col * square_w, 9),
                            round(border_h + row * square_h, 9),
                            0,
                        ],
                    }
                )
                i += 1

    required = {"width": width + 2 * EDGE_CLEARANCE_MM, "height": height + 2 * EDGE_CLEARANCE_MM}
    available = {"width": page_w, "height": page_h}
    if required["width"] > page_w or required["height"] > page_h:
        raise FitError(
            "page_fit",
            ["board"],
            "The compensated board does not fit within the page clearance",
            required,
            available,
        )
    target = Rect(origin_x, origin_y, width, height)
    if label_band and label_band.y + label_band.height > page_h - EDGE_CLEARANCE_MM:
        raise FitError(
            "annotation_fit",
            ["board", "show_ids"],
            "Marker ID labels do not fit outside the calibration targets",
            {"height": label_band.height + 1},
            {"height": (page_h - height) / 2 - EDGE_CLEARANCE_MM},
        )

    annotation_gap = 2.0
    ruler_template = ruler_geometry()
    annotations: dict[str, Rect] = {}
    top_y = EDGE_CLEARANCE_MM
    if req.annotations.show_ruler:
        w, h = ruler_template.bounds.width, ruler_template.bounds.height
        if top_y + h + annotation_gap > target.y:
            raise FitError(
                "annotation_fit",
                ["annotations", "ruler"],
                "No safe top margin is available for the scale ruler",
                {"width": w, "height": h},
                available,
            )
        annotations["ruler"] = Rect((page_w - w) / 2, top_y, w, h)

    # Textual metadata belongs to a stable bottom rail. The coordinate frame is
    # board-attached geometry and intentionally overlays the calibration target.
    metadata_width = min(150.0, page_w - 2 * EDGE_CLEARANCE_MM)
    bottom_specs = []
    if req.annotations.show_parameters:
        bottom_specs.append(("parameters", metadata_width, 4.0))
    bottom_y = page_h - EDGE_CLEARANCE_MM
    occupied_bottom = (
        label_band.y + label_band.height if label_band is not None else target.y + target.height
    )
    for name, w, h in reversed(bottom_specs):
        x = (page_w - w) / 2
        if bottom_y - h - annotation_gap < occupied_bottom:
            raise FitError(
                "annotation_fit",
                ["annotations", name],
                f"No safe bottom margin is available for {name}",
                {"width": w, "height": h},
                available,
            )
        bottom_y -= h
        annotations[name] = Rect(x, bottom_y, w, h)
        bottom_y -= annotation_gap

    frame = None
    if req.annotations.show_frame_legend:
        frame = frame_geometry(target.x, target.y)
        bounds = frame.bounds
        if (
            bounds.x < EDGE_CLEARANCE_MM
            or bounds.y < EDGE_CLEARANCE_MM
            or bounds.x + bounds.width > page_w - EDGE_CLEARANCE_MM
            or bounds.y + bounds.height > page_h - EDGE_CLEARANCE_MM
        ):
            raise FitError(
                "annotation_fit",
                ["annotations", "frame_legend"],
                "The coordinate frame axes do not fit within the page clearance",
                {"width": bounds.width, "height": bounds.height},
                {"width": page_w - 2 * EDGE_CLEARANCE_MM, "height": page_h - 2 * EDGE_CLEARANCE_MM},
            )
        annotations["frame_legend"] = bounds

    ruler = None
    if "ruler" in annotations:
        box = annotations["ruler"]
        ruler = ruler_geometry(box.x, box.y)

    return Scene(
        request=req,
        page=Rect(0, 0, page_w, page_h),
        target=target,
        black_rects=tuple(black),
        features=tuple(features),
        white_rects=tuple(white),
        marker_rects=tuple(marker_backgrounds),
        marker_white_rects=tuple(marker_white),
        marker_labels=tuple(labels),
        annotation_rects=annotations,
        ruler=ruler,
        frame=frame,
        transform=_pose(req),
    )
