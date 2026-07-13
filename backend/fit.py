from __future__ import annotations

import math
from collections.abc import Iterable

from .constants import EDGE_CLEARANCE_MM, PAPER_SIZES_MM
from .errors import FitError
from .models import (
    ArucoBoard,
    CharucoBoard,
    Checkerboard,
    FitChange,
    FitResponse,
    GenerateRequest,
)
from .scene import build_scene


FITTABLE_FIELDS = {
    "aruco": ("marker_size_mm", "separation_mm"),
    "charuco": ("square_size_mm", "marker_size_mm"),
    "checkerboard": ("square_size_mm", "border_mm"),
}

COUNT_FIELDS = {
    "aruco": ("columns", "rows", 1),
    "charuco": ("squares_x", "squares_y", 2),
    "checkerboard": ("squares_x", "squares_y", 2),
}


def _down_tenth(value: float) -> float:
    return math.floor((value + 1e-9) * 10) / 10


def _clean_down(value: float) -> float:
    """Prefer whole millimetres, retaining tenths only below 1 mm."""
    integer = math.floor(value + 1e-9)
    return float(integer) if integer >= 1 else _down_tenth(value)


def _scaled_clean(req: GenerateRequest, factor: float) -> GenerateRequest | None:
    board = req.board
    values = board.model_dump()
    for field in FITTABLE_FIELDS[board.type]:
        value = _clean_down(float(values[field]) * factor)
        if field == "border_mm":
            value = max(0.0, value)
        elif value < 0.1:
            return None
        values[field] = value
    if isinstance(board, CharucoBoard) and values["marker_size_mm"] >= values["square_size_mm"]:
        return None
    try:
        fitted_board = type(board).model_validate(values)
    except ValueError:
        return None
    return req.model_copy(update={"board": fitted_board})


def _geometry_candidates(req: GenerateRequest) -> Iterable[GenerateRequest]:
    """Yield clean geometry from largest to smallest without ever upscaling."""
    factors = {1.0}
    for field in FITTABLE_FIELDS[req.board.type]:
        old = float(getattr(req.board, field))
        if old <= 0:
            continue
        clean_values = [float(value) for value in range(1, math.floor(old) + 1)]
        clean_values.extend(value / 10 for value in range(1, 10))
        factors.update(value / old for value in clean_values if value <= old)

    seen: set[tuple[float, ...]] = set()
    for factor in sorted(factors, reverse=True):
        candidate = _scaled_clean(req, factor)
        if candidate is None:
            continue
        key = tuple(
            float(getattr(candidate.board, field)) for field in FITTABLE_FIELDS[req.board.type]
        )
        if key in seen:
            continue
        seen.add(key)
        yield candidate


def _with_counts(req: GenerateRequest, x_count: int, y_count: int) -> GenerateRequest:
    x_field, y_field, _ = COUNT_FIELDS[req.board.type]
    values = req.board.model_dump()
    values[x_field] = x_count
    values[y_field] = y_count
    return req.model_copy(update={"board": type(req.board).model_validate(values)})


def _count_candidates(req: GenerateRequest) -> list[tuple[int, int]]:
    x_field, y_field, minimum = COUNT_FIELDS[req.board.type]
    original_x = int(getattr(req.board, x_field))
    original_y = int(getattr(req.board, y_field))
    candidates = [
        (x_count, y_count)
        for x_count in range(minimum, original_x + 1)
        for y_count in range(minimum, original_y + 1)
    ]
    candidates.sort(
        key=lambda counts: (
            counts[0] * counts[1],
            min(counts[0] / original_x, counts[1] / original_y),
            counts[0] / original_x + counts[1] / original_y,
        ),
        reverse=True,
    )
    return candidates


def _target_dimensions(req: GenerateRequest) -> tuple[float, float]:
    board = req.board
    sx = req.print_compensation.x_percent / 100
    sy = req.print_compensation.y_percent / 100
    if isinstance(board, ArucoBoard):
        width = board.columns * board.marker_size_mm + (board.columns - 1) * board.separation_mm
        height = board.rows * board.marker_size_mm + (board.rows - 1) * board.separation_mm
    elif isinstance(board, CharucoBoard):
        width = board.squares_x * board.square_size_mm
        height = board.squares_y * board.square_size_mm
    else:
        assert isinstance(board, Checkerboard)
        width = board.squares_x * board.square_size_mm + 2 * board.border_mm
        height = board.squares_y * board.square_size_mm + 2 * board.border_mm
    return width * sx, height * sy


def _passes_page_clearance(req: GenerateRequest) -> bool:
    page_width, page_height = PAPER_SIZES_MM[req.page.paper_size]
    if req.page.orientation == "landscape":
        page_width, page_height = page_height, page_width
    width, height = _target_dimensions(req)
    return (
        width + 2 * EDGE_CLEARANCE_MM <= page_width
        and height + 2 * EDGE_CLEARANCE_MM <= page_height
    )


def _scene_accepts(req: GenerateRequest) -> bool:
    if not _passes_page_clearance(req):
        return False
    try:
        build_scene(req)
    except FitError as error:
        if error.code not in {"page_fit", "annotation_fit"}:
            raise
        return False
    return True


def _fit_counts(req: GenerateRequest) -> GenerateRequest | None:
    for x_count, y_count in _count_candidates(req):
        candidate = _with_counts(req, x_count, y_count)
        if _scene_accepts(candidate):
            return candidate
    return None


def fit_request(req: GenerateRequest) -> FitResponse:
    try:
        build_scene(req)
        return FitResponse(request=req, adjusted=False, scale_factor=1.0)
    except FitError as initial_error:
        if initial_error.code not in {"page_fit", "annotation_fit"}:
            raise

    best: GenerateRequest | None = None
    minimum = COUNT_FIELDS[req.board.type][2]
    for geometry in _geometry_candidates(req):
        # If the smallest possible grid cannot fit, larger count combinations
        # cannot fit either. This keeps large-grid fitting deterministic and fast.
        smallest = _with_counts(geometry, minimum, minimum)
        if not _scene_accepts(smallest):
            continue
        best = _fit_counts(geometry)
        if best is not None:
            break

    if best is None:
        raise FitError(
            "auto_fit_impossible",
            ["board"],
            "The board cannot fit safely even after reducing clean dimensions and grid counts",
        )

    changes = []
    ratios = []
    before = req.board.model_dump()
    after = best.board.model_dump()
    adjustable = (*COUNT_FIELDS[req.board.type][:2], *FITTABLE_FIELDS[req.board.type])
    for field in adjustable:
        old, new = float(before[field]), float(after[field])
        if old != new:
            changes.append(FitChange(field=f"board.{field}", before=old, after=new))
            if field in FITTABLE_FIELDS[req.board.type] and old:
                ratios.append(new / old)
    applied = min(ratios, default=1.0)
    return FitResponse(
        request=best,
        adjusted=True,
        scale_factor=round(applied, 6),
        changes=tuple(changes),
    )
