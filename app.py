"""
ArUco Grid Generator - Streamlit Version

A web application for generating printable ArUco marker grids for computer vision and robotics.
"""

import hashlib
import io
import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np
import streamlit as st
from pdf2image import convert_from_bytes
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A1, A2, A3, A4, legal, letter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from scipy.spatial.transform import Rotation as R_scipy

# Constants
PT_TO_MM = 25.4 / 72
MAX_DPI = 600
MAX_GRID_SIZE = 100  # Maximum rows or columns
MAX_MARKER_SIZE = 200  # mm
DEFAULT_LOGO_PATH = "static/match.png"
DEFAULT_FAVICON_PATH = "static/matchfavicon.png"

# Shared paper sizes dictionary
PAPER_SIZES = {
    "A4": A4,
    "A3": A3,
    "A2": A2,
    "A1": A1,
    "Letter": letter,
    "Legal": legal,
}

# Default settings for dummy preview
DEFAULT_SETTINGS = {
    "board_type": "aruco_grid",
    "paper_size": "A4",
    "orientation": "portrait",
    "dictionary": "DICT_5X5_250",
    "rows": 7,
    "cols": 5,
    "marker_size_mm": 30,
    "separation_mm": 10,
    "show_ids": True,
    "show_scale": True,
    "show_params": True,
    "show_coordsys": False,
    "vertical_scale": 100.0,
    "horizontal_scale": 100.0,
    "marker_id_font_size": 24,
}


def get_settings_hash(data: Dict[str, Any]) -> str:
    """Get a hash of settings to detect changes."""
    # Sort keys for consistent hashing
    sorted_items = sorted(data.items())
    hash_str = str(sorted_items)
    return hashlib.md5(hash_str.encode()).hexdigest()


def get_page_dimensions(paper_size: str, orientation: str) -> Tuple[float, float]:
    """Get page dimensions in mm using reportlab pagesizes."""
    pagesize = PAPER_SIZES.get(paper_size, A4)

    width_pt, height_pt = pagesize
    width_mm = width_pt * PT_TO_MM
    height_mm = height_pt * PT_TO_MM

    if orientation == "portrait":
        return width_mm, height_mm
    return height_mm, width_mm


def get_pagesize(paper_size: str, orientation: str) -> Tuple[float, float]:
    """Get page dimensions in points for reportlab PDF generation."""
    pagesize = PAPER_SIZES.get(paper_size, A4)

    if orientation == "portrait":
        return pagesize
    return (pagesize[1], pagesize[0])


@st.cache_data
def calculate_transformation(
    data: Dict[str, Any],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calculate transformation matrix from grid parameters."""
    paper_size = data.get("paper_size", "A4")
    orientation = data.get("orientation", "portrait")
    base_translation = data.get("base_translation", [0, 0, 0])
    base_rotation = data.get("base_rotation", [0, 0, 0])

    width_mm, height_mm = get_page_dimensions(paper_size, orientation)

    tx, ty, tz = base_translation
    roll, pitch, yaw = [math.radians(r) for r in base_rotation]

    R_default = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]])

    Rx = np.array(
        [
            [1, 0, 0],
            [0, math.cos(roll), -math.sin(roll)],
            [0, math.sin(roll), math.cos(roll)],
        ]
    )
    Ry = np.array(
        [
            [math.cos(pitch), 0, math.sin(pitch)],
            [0, 1, 0],
            [-math.sin(pitch), 0, math.cos(pitch)],
        ]
    )
    Rz = np.array(
        [
            [math.cos(yaw), -math.sin(yaw), 0],
            [math.sin(yaw), math.cos(yaw), 0],
            [0, 0, 1],
        ]
    )
    R_user = Rz @ Ry @ Rx

    R = R_user @ R_default

    t = np.array([-width_mm / 2 - tx, height_mm / 2 - ty, -tz])

    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = t

    t_m = t / 1000

    r = R_scipy.from_matrix(R)
    quat = r.as_quat()

    return T, t_m, quat


def generate_aruco_grid(
    data: Dict[str, Any], low_res: bool = False, draw_overlays: bool = True
) -> Image.Image:
    """Generate an ArUco grid image based on the provided parameters."""
    dictionary_name = data.get("dictionary", "DICT_5X5_250")
    rows = data.get("rows", 5)
    cols = data.get("cols", 7)
    marker_size_mm = data.get("marker_size_mm", 30)
    separation_mm = data.get("separation_mm", 10)
    paper_size = data.get("paper_size", "A4")
    orientation = data.get("orientation", "portrait")
    show_ids = data.get("show_ids", True)
    show_scale = data.get("show_scale", True)
    show_coordsys = data.get("show_coordsys", False)
    marker_id_font_size = data.get("marker_id_font_size", None)

    aruco_dict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dictionary_name))

    max_markers = aruco_dict.bytesList.shape[0]
    total_markers = rows * cols
    if total_markers > max_markers:
        raise ValueError(
            f"Grid size ({rows}×{cols}={total_markers}) exceeds dictionary capacity ({max_markers}). "
            f"Please reduce rows or columns, or use a dictionary with more markers."
        )

    width_mm, height_mm = get_page_dimensions(paper_size, orientation)

    total_width_mm = cols * marker_size_mm + (cols - 1) * separation_mm
    total_height_mm = rows * marker_size_mm + (rows - 1) * separation_mm

    if total_width_mm > width_mm or total_height_mm > height_mm:
        raise ValueError(
            f"Grid size ({total_width_mm:.1f}mm × {total_height_mm:.1f}mm) exceeds "
            f"page size ({width_mm:.1f}mm × {height_mm:.1f}mm). "
            f"Please reduce marker size, separation, rows, or columns, or use larger paper."
        )

    dpi = 72 if low_res else 300
    px_per_mm = dpi / 25.4

    marker_size_px = int(marker_size_mm * px_per_mm)
    separation_px = int(separation_mm * px_per_mm)

    total_width_px = cols * marker_size_px + (cols - 1) * separation_px
    total_height_px = rows * marker_size_px + (rows - 1) * separation_px

    img_width_px = int(width_mm * px_per_mm)
    img_height_px = int(height_mm * px_per_mm)
    img = np.ones((img_height_px, img_width_px, 3), dtype=np.uint8) * 255

    offset_x = (img_width_px - total_width_px) // 2
    offset_y = (img_height_px - total_height_px) // 2

    marker_id = 0
    for r in range(rows):
        for c in range(cols):
            marker_img = cv2.aruco.generateImageMarker(
                aruco_dict, marker_id, marker_size_px
            )
            marker_img = cv2.cvtColor(marker_img, cv2.COLOR_GRAY2BGR)

            x = offset_x + c * (marker_size_px + separation_px)
            y = offset_y + r * (marker_size_px + separation_px)

            img[y : y + marker_size_px, x : x + marker_size_px] = marker_img

            marker_id += 1

    pil_img = Image.fromarray(img)

    if show_ids:
        draw = ImageDraw.Draw(pil_img)
        if marker_id_font_size is not None:
            font_size = marker_id_font_size
        else:
            font_size = (
                min(12, marker_size_px // 7)
                if low_res
                else min(24, marker_size_px // 7)
            )

        font = _get_font(font_size)

        marker_id = 0
        for r in range(rows):
            for c in range(cols):
                x = (
                    offset_x
                    + c * (marker_size_px + separation_px)
                    + marker_size_px // 2
                )
                y = (
                    offset_y
                    + r * (marker_size_px + separation_px)
                    + marker_size_px
                    + font_size
                )
                draw.text(
                    (x, y), str(marker_id), fill=(0, 0, 0), font=font, anchor="mm"
                )
                marker_id += 1

    if draw_overlays:
        if show_scale:
            draw = ImageDraw.Draw(pil_img)
            ruler_y = img_height_px - 20
            ruler_length_px = 100 * px_per_mm
            start_x = 10
            for i in range(0, 101, 1):
                x = start_x + i * px_per_mm
                if i % 10 == 0:
                    draw.line(
                        (x, ruler_y, x, ruler_y + 15), fill=(128, 128, 128), width=1
                    )
                else:
                    draw.line(
                        (x, ruler_y, x, ruler_y + 8), fill=(128, 128, 128), width=1
                    )
            draw.text(
                (start_x + ruler_length_px + 5, ruler_y - 5),
                "10 cm",
                fill=(128, 128, 128),
            )

        if data.get("show_params", True):
            font_size = 6
            font = _get_font(font_size)
            left_x = img_width_px - 140
            right_x = img_width_px - 60
            y_start = img_height_px - 20
            draw.text(
                (left_x, y_start),
                f"Paper: {data.get('paper_size')} {data.get('orientation')}",
                fill=(0, 0, 0),
                font=font,
            )
            draw.text(
                (right_x, y_start),
                f"Dict: {data.get('dictionary')}",
                fill=(0, 0, 0),
                font=font,
            )
            draw.text(
                (left_x, y_start + 5),
                f"Rows: {data.get('rows')}",
                fill=(0, 0, 0),
                font=font,
            )
            draw.text(
                (right_x, y_start + 5),
                f"Cols: {data.get('cols')}",
                fill=(0, 0, 0),
                font=font,
            )
            draw.text(
                (left_x, y_start + 10),
                f"Size: {data.get('marker_size_mm')}mm",
                fill=(0, 0, 0),
                font=font,
            )
            draw.text(
                (right_x, y_start + 10),
                f"Sep: {data.get('separation_mm')}mm",
                fill=(0, 0, 0),
                font=font,
            )

    if show_coordsys and draw_overlays:
        draw = ImageDraw.Draw(pil_img)
        cx = img_width_px // 2
        cy = img_height_px // 2
        axis_length = 50
        font_size = 12
        font = _get_font(font_size)

        draw.line(
            (cx - axis_length, cy, cx + axis_length, cy), fill=(255, 0, 0), width=2
        )
        draw.line(
            (cx + axis_length, cy, cx + axis_length - 5, cy - 3),
            fill=(255, 0, 0),
            width=2,
        )
        draw.line(
            (cx + axis_length, cy, cx + axis_length - 5, cy + 3),
            fill=(255, 0, 0),
            width=2,
        )
        draw.text((cx + axis_length + 5, cy - 10), "X", fill=(255, 0, 0), font=font)

        draw.line(
            (cx, cy - axis_length, cx, cy + axis_length), fill=(0, 255, 0), width=2
        )
        draw.line(
            (cx, cy - axis_length, cx - 3, cy - axis_length + 5),
            fill=(0, 255, 0),
            width=2,
        )
        draw.line(
            (cx, cy - axis_length, cx + 3, cy - axis_length + 5),
            fill=(0, 255, 0),
            width=2,
        )
        draw.text((cx + 5, cy - axis_length - 15), "Y", fill=(0, 255, 0), font=font)

    if low_res:
        draw = ImageDraw.Draw(pil_img)
        width, height = pil_img.size
        grey = (128, 128, 128)
        draw.line((0, 0, width - 1, 0), fill=grey, width=2)
        draw.line((0, height - 1, width - 1, height - 1), fill=grey, width=2)
        draw.line((0, 0, 0, height - 1), fill=grey, width=2)
        draw.line((width - 1, 0, width - 1, height - 1), fill=grey, width=2)

    vertical_scale = data.get("vertical_scale", 100.0) / 100.0
    horizontal_scale = data.get("horizontal_scale", 100.0) / 100.0

    if vertical_scale != 1.0 or horizontal_scale != 1.0:
        new_width = int(pil_img.width * horizontal_scale)
        new_height = int(pil_img.height * vertical_scale)
        pil_img = pil_img.resize((new_width, new_height), Image.LANCZOS)

    return pil_img


def generate_charuco_board(
    data: Dict[str, Any], low_res: bool = False, draw_overlays: bool = True
) -> Image.Image:
    """Generate a CharUco board image based on the provided parameters."""
    import logging

    logger = logging.getLogger(__name__)

    # Debug: Log OpenCV version and available aruco attributes
    logger.info(f"OpenCV version: {cv2.__version__}")
    aruco_attrs = [a for a in dir(cv2.aruco) if "Charuco" in a]
    logger.info(f"OpenCV CharUco attributes available: {aruco_attrs}")

    dictionary_name = data.get("dictionary", "DICT_5X5_250")
    squares_x = data.get("squares_x", 5)
    squares_y = data.get("squares_y", 7)
    square_size_mm = data.get("square_size_mm", 30)
    marker_size_mm = data.get("marker_size_mm", 30)
    paper_size = data.get("paper_size", "A4")
    orientation = data.get("orientation", "portrait")
    show_ids = data.get("show_ids", True)
    show_scale = data.get("show_scale", True)
    show_params = data.get("show_params", True)

    # DEBUG: Log key parameters that affect board generation
    logger.info(
        f"CharUco params: squares_x={squares_x}, squares_y={squares_y}, square_size={square_size_mm}, marker_size={marker_size_mm}"
    )

    # DIAGNOSIS 1: Check if marker size is too large relative to square size
    if marker_size_mm >= square_size_mm:
        logger.warning(
            f"Marker size ({marker_size_mm}mm) >= square size ({square_size_mm}mm) - markers will overlap with checkerboard squares!"
        )
        # In production, could raise an error or adjust automatically
        # For now, we'll let it proceed but the output will have overlapping markers

    # DIAGNOSIS 2: Calculate required markers and dictionary capacity
    num_corners = (squares_x - 1) * (squares_y - 1)
    logger.info(f"CharUco board requires {num_corners} markers (corners)")

    aruco_dict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dictionary_name))

    # Debug: Check dictionary properties
    logger.info(f"Dictionary type: {type(aruco_dict)}")
    logger.info(f"Dictionary bytesList shape: {aruco_dict.bytesList.shape}")

    # Calculate number of markers needed
    # CharUco board has (squares_x-1) * (squares_y-1) corners
    # and each corner needs a marker
    num_corners = (squares_x - 1) * (squares_y - 1)
    max_markers = aruco_dict.bytesList.shape[0]

    if num_corners > max_markers:
        raise ValueError(
            f"CharUco board requires {num_corners} markers but dictionary only has {max_markers}. "
            f"Please use a dictionary with more markers or reduce the number of squares."
        )

    width_mm, height_mm = get_page_dimensions(paper_size, orientation)

    # Calculate total board size
    total_width_mm = squares_x * square_size_mm
    total_height_mm = squares_y * square_size_mm

    if total_width_mm > width_mm or total_height_mm > height_mm:
        raise ValueError(
            f"Board size ({total_width_mm:.1f}mm × {total_height_mm:.1f}mm) exceeds "
            f"page size ({width_mm:.1f}mm × {height_mm:.1f}mm). "
            f"Please reduce square size or number of squares, or use larger paper."
        )

    dpi = 72 if low_res else 300
    px_per_mm = dpi / 25.4

    # Calculate image dimensions
    img_width_px = int(width_mm * px_per_mm)
    img_height_px = int(height_mm * px_per_mm)

    # Calculate board pixel size
    board_width_px = int(total_width_mm * px_per_mm)
    board_height_px = int(total_height_mm * px_per_mm)

    # Try OpenCV's built-in CharUco board generation first
    use_opencv = False
    opencv_error = None
    try:
        if hasattr(cv2.aruco, "CharucoBoard_create"):
            logger.info("Attempting cv2.aruco.CharucoBoard_create...")
            board = cv2.aruco.CharucoBoard_create(
                squares_x,
                squares_y,
                float(square_size_mm),
                float(marker_size_mm),
                aruco_dict,
            )
            use_opencv = True
            logger.info("Using OpenCV CharucoBoard_create - SUCCESS")
        elif hasattr(cv2.aruco, "CharucoBoard"):
            logger.info("Attempting cv2.aruco.CharucoBoard class...")
            board = cv2.aruco.CharucoBoard(
                (squares_x, squares_y),
                float(square_size_mm),
                float(marker_size_mm),
                aruco_dict,
            )
            use_opencv = True
            logger.info("Using OpenCV CharucoBoard class - SUCCESS")
    except Exception as e:
        opencv_error = str(e)
        logger.warning(f"OpenCV CharUco creation failed: {type(e).__name__}: {e}")
        use_opencv = False

    if use_opencv:
        # DIAGNOSIS 5: Check if generateImage works
        try:
            board_img = board.generateImage((board_width_px, board_height_px))
            logger.info(
                f"OpenCV generateImage succeeded, board_img shape: {board_img.shape}"
            )
        except Exception as e:
            logger.warning(f"OpenCV generateImage failed: {type(e).__name__}: {e}")
            use_opencv = False
            opencv_error = f"generateImage failed: {e}"

    if use_opencv:
        # Use OpenCV's built-in board generation
        board_img = board.generateImage((board_width_px, board_height_px))
    else:
        # Manual CharUco board generation (fallback when OpenCV doesn't have CharUco support)
        logger.info("FALLBACK: Generating CharUco board manually")

        # Create white canvas for the board
        board_img = np.ones((board_height_px, board_width_px), dtype=np.uint8) * 255

        square_size_px = int(square_size_mm * px_per_mm)
        marker_size_px = int(marker_size_mm * px_per_mm)

        # DIAGNOSIS 3: Check spacing between adjacent markers in manual generation
        spacing_px = square_size_px  # Distance between marker centers
        logger.info(
            f"Manual generation: board_size=({board_width_px}x{board_height_px}px), square_size_px={square_size_px}, marker_size_px={marker_size_px}"
        )
        logger.info(f"Distance between adjacent marker centers: {spacing_px}px")
        if marker_size_px > spacing_px:
            logger.warning(
                f"PROBLEM: marker_size_px ({marker_size_px}) > spacing ({spacing_px}) - markers will overlap!"
            )
        elif marker_size_px > spacing_px * 0.8:
            logger.warning(
                f"WARNING: marker_size_px ({marker_size_px}) > 80% of spacing ({spacing_px}) - markers may touch!"
            )

        # Draw checkerboard squares
        for row in range(squares_y):
            for col in range(squares_x):
                x = col * square_size_px
                y = row * square_size_px
                # Alternate between black and white
                if (row + col) % 2 == 0:
                    board_img[y : y + square_size_px, x : x + square_size_px] = 0

        # Place ArUco markers at corners (except on outer boundary)
        marker_id = 0
        for row in range(squares_y - 1):
            for col in range(squares_x - 1):
                # Calculate marker position (at the intersection of 4 squares)
                x = (col + 1) * square_size_px
                y = (row + 1) * square_size_px

                # Generate marker image
                marker_img = cv2.aruco.generateImageMarker(
                    aruco_dict, marker_id, marker_size_px
                )

                # Calculate marker offset to center it at intersection
                offset_x = x - marker_size_px // 2
                offset_y = y - marker_size_px // 2

                # Ensure marker stays within bounds
                if (
                    offset_y + marker_size_px <= board_height_px
                    and offset_x + marker_size_px <= board_width_px
                    and offset_y >= 0
                    and offset_x >= 0
                ):
                    # Simply overlay the marker directly (replacing underlying pixels)
                    board_img[
                        offset_y : offset_y + marker_size_px,
                        offset_x : offset_x + marker_size_px,
                    ] = marker_img

                marker_id += 1

    # Create white canvas and paste board
    img = np.ones((img_height_px, img_width_px, 3), dtype=np.uint8) * 255

    offset_x = (img_width_px - board_width_px) // 2
    offset_y = (img_height_px - board_height_px) // 2

    # Convert board_img to 3 channels if needed
    if len(board_img.shape) == 2:
        board_img = cv2.cvtColor(board_img, cv2.COLOR_GRAY2BGR)

    img[offset_y : offset_y + board_height_px, offset_x : offset_x + board_width_px] = (
        board_img
    )

    pil_img = Image.fromarray(img)

    if draw_overlays:
        if show_scale:
            draw = ImageDraw.Draw(pil_img)
            ruler_y = img_height_px - 20
            ruler_length_px = 100 * px_per_mm
            start_x = 10
            for i in range(0, 101, 1):
                x = start_x + i * px_per_mm
                if i % 10 == 0:
                    draw.line(
                        (x, ruler_y, x, ruler_y + 15), fill=(128, 128, 128), width=1
                    )
                else:
                    draw.line(
                        (x, ruler_y, x, ruler_y + 8), fill=(128, 128, 128), width=1
                    )
            draw.text(
                (start_x + ruler_length_px + 5, ruler_y - 5),
                "10 cm",
                fill=(128, 128, 128),
            )

        if show_params:
            font_size = 6
            font = _get_font(font_size)
            left_x = img_width_px - 140
            right_x = img_width_px - 60
            y_start = img_height_px - 20
            draw.text(
                (left_x, y_start),
                f"Paper: {data.get('paper_size')} {data.get('orientation')}",
                fill=(0, 0, 0),
                font=font,
            )
            draw.text(
                (right_x, y_start),
                f"Type: CharUco",
                fill=(0, 0, 0),
                font=font,
            )
            draw.text(
                (left_x, y_start + 5),
                f"Squares X: {squares_x}",
                fill=(0, 0, 0),
                font=font,
            )
            draw.text(
                (right_x, y_start + 5),
                f"Squares Y: {squares_y}",
                fill=(0, 0, 0),
                font=font,
            )
            draw.text(
                (left_x, y_start + 10),
                f"Square: {square_size_mm}mm",
                fill=(0, 0, 0),
                font=font,
            )
            draw.text(
                (right_x, y_start + 10),
                f"Marker: {marker_size_mm}mm",
                fill=(0, 0, 0),
                font=font,
            )

    if low_res:
        draw = ImageDraw.Draw(pil_img)
        width, height = pil_img.size
        grey = (128, 128, 128)
        draw.line((0, 0, width - 1, 0), fill=grey, width=2)
        draw.line((0, height - 1, width - 1, height - 1), fill=grey, width=2)
        draw.line((0, 0, 0, height - 1), fill=grey, width=2)
        draw.line((width - 1, 0, width - 1, height - 1), fill=grey, width=2)

    vertical_scale = data.get("vertical_scale", 100.0) / 100.0
    horizontal_scale = data.get("horizontal_scale", 100.0) / 100.0

    if vertical_scale != 1.0 or horizontal_scale != 1.0:
        new_width = int(pil_img.width * horizontal_scale)
        new_height = int(pil_img.height * vertical_scale)
        pil_img = pil_img.resize((new_width, new_height), Image.LANCZOS)

    return pil_img


def generate_checkerboard(
    data: Dict[str, Any], low_res: bool = False, draw_overlays: bool = True
) -> Image.Image:
    """Generate a Checkerboard image based on the provided parameters."""
    squares_x = data.get("squares_x", 5)
    squares_y = data.get("squares_y", 8)
    square_size_mm = data.get("square_size_mm", 30)
    border_mm = data.get("border_mm", 20)
    paper_size = data.get("paper_size", "A4")
    orientation = data.get("orientation", "portrait")
    show_scale = data.get("show_scale", True)
    show_params = data.get("show_params", True)

    width_mm, height_mm = get_page_dimensions(paper_size, orientation)

    # Calculate total board size (including border)
    total_width_mm = squares_x * square_size_mm + 2 * border_mm
    total_height_mm = squares_y * square_size_mm + 2 * border_mm

    if total_width_mm > width_mm or total_height_mm > height_mm:
        raise ValueError(
            f"Board size ({total_width_mm:.1f}mm × {total_height_mm:.1f}mm) exceeds "
            f"page size ({width_mm:.1f}mm × {height_mm:.1f}mm). "
            f"Please reduce square size, number of squares, or border, or use larger paper."
        )

    dpi = 72 if low_res else 300
    px_per_mm = dpi / 25.4

    # Calculate image dimensions
    img_width_px = int(width_mm * px_per_mm)
    img_height_px = int(height_mm * px_per_mm)

    # Create white canvas
    img = np.ones((img_height_px, img_width_px, 3), dtype=np.uint8) * 255

    # Calculate board area
    board_width_px = int(squares_x * square_size_mm * px_per_mm)
    board_height_px = int(squares_y * square_size_mm * px_per_mm)
    border_px = int(border_mm * px_per_mm)

    # Calculate offset to center the board
    offset_x = (img_width_px - board_width_px) // 2
    offset_y = (img_height_px - board_height_px) // 2

    # Draw checkerboard
    square_px = int(square_size_mm * px_per_mm)

    for row in range(squares_y):
        for col in range(squares_x):
            # Alternate between black and white
            if (row + col) % 2 == 0:
                x = offset_x + col * square_px
                y = offset_y + row * square_px
                img[y : y + square_px, x : x + square_px] = 0  # Black

    pil_img = Image.fromarray(img)

    if draw_overlays:
        if show_scale:
            draw = ImageDraw.Draw(pil_img)
            ruler_y = img_height_px - 20
            ruler_length_px = 100 * px_per_mm
            start_x = 10
            for i in range(0, 101, 1):
                x = start_x + i * px_per_mm
                if i % 10 == 0:
                    draw.line(
                        (x, ruler_y, x, ruler_y + 15), fill=(128, 128, 128), width=1
                    )
                else:
                    draw.line(
                        (x, ruler_y, x, ruler_y + 8), fill=(128, 128, 128), width=1
                    )
            draw.text(
                (start_x + ruler_length_px + 5, ruler_y - 5),
                "10 cm",
                fill=(128, 128, 128),
            )

        if show_params:
            font_size = 6
            font = _get_font(font_size)
            left_x = img_width_px - 140
            right_x = img_width_px - 60
            y_start = img_height_px - 20
            draw.text(
                (left_x, y_start),
                f"Paper: {data.get('paper_size')} {data.get('orientation')}",
                fill=(0, 0, 0),
                font=font,
            )
            draw.text(
                (right_x, y_start),
                f"Type: Checker",
                fill=(0, 0, 0),
                font=font,
            )
            draw.text(
                (left_x, y_start + 5),
                f"Squares X: {squares_x}",
                fill=(0, 0, 0),
                font=font,
            )
            draw.text(
                (right_x, y_start + 5),
                f"Squares Y: {squares_y}",
                fill=(0, 0, 0),
                font=font,
            )
            draw.text(
                (left_x, y_start + 10),
                f"Square: {square_size_mm}mm",
                fill=(0, 0, 0),
                font=font,
            )
            draw.text(
                (right_x, y_start + 10),
                f"Border: {border_mm}mm",
                fill=(0, 0, 0),
                font=font,
            )

    if low_res:
        draw = ImageDraw.Draw(pil_img)
        width, height = pil_img.size
        grey = (128, 128, 128)
        draw.line((0, 0, width - 1, 0), fill=grey, width=2)
        draw.line((0, height - 1, width - 1, height - 1), fill=grey, width=2)
        draw.line((0, 0, 0, height - 1), fill=grey, width=2)
        draw.line((width - 1, 0, width - 1, height - 1), fill=grey, width=2)

    vertical_scale = data.get("vertical_scale", 100.0) / 100.0
    horizontal_scale = data.get("horizontal_scale", 100.0) / 100.0

    if vertical_scale != 1.0 or horizontal_scale != 1.0:
        new_width = int(pil_img.width * horizontal_scale)
        new_height = int(pil_img.height * vertical_scale)
        pil_img = pil_img.resize((new_width, new_height), Image.LANCZOS)

    return pil_img


def _get_font(font_size: int) -> ImageFont.FreeTypeFont:
    """Get font with fallback to default."""
    font_paths = [
        "arial.ttf",
        "Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for font_path in font_paths:
        try:
            return ImageFont.truetype(font_path, font_size)
        except OSError:
            continue
    return ImageFont.load_default()


@st.cache_data
def generate_pdf(data: Dict[str, Any]) -> io.BytesIO:
    """Generate a PDF file with the calibration board."""
    show_scale = data.get("show_scale", True)
    show_params = data.get("show_params", True)
    board_type = data.get("board_type", "aruco_grid")

    # Generate the appropriate board type
    if board_type == "charuco":
        img = generate_charuco_board(data, low_res=False, draw_overlays=False)
    elif board_type == "checkerboard":
        img = generate_checkerboard(data, low_res=False, draw_overlays=False)
    else:
        img = generate_aruco_grid(data, low_res=False, draw_overlays=False)

    paper_size = data.get("paper_size", "A4")
    orientation = data.get("orientation", "portrait")
    pagesize = get_pagesize(paper_size, orientation)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=pagesize)

    width, height = pagesize

    img_width, img_height = img.size
    pt_per_px = 72.0 / 300
    img_width_pt = img_width * pt_per_px
    img_height_pt = img_height * pt_per_px

    x_offset = (width - img_width_pt) / 2
    y_offset = (height - img_height_pt) / 2
    c.drawInlineImage(img, x_offset, y_offset, width=img_width_pt, height=img_height_pt)

    if show_scale:
        c.setFont("Helvetica", 8)
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        start_x = 20
        ruler_y = 20
        for i in range(0, 101, 1):
            x = start_x + i * mm
            if i % 10 == 0:
                c.line(x, ruler_y, x, ruler_y + 8)
            else:
                c.line(x, ruler_y, x, ruler_y + 4)
        c.drawString(start_x + 100 * mm + 5, ruler_y, "10 cm")

    if show_params:
        c.setFont("Helvetica", 5)
        left_x = width - 150
        right_x = width - 70
        y_start = 15
        c.drawString(left_x, y_start, f"Paper: {paper_size} {orientation}")

        # Add board type specific params
        if board_type == "charuco":
            c.drawString(right_x, y_start, f"Type: CharUco")
            c.drawString(left_x, y_start + 5, f"Squares X: {data.get('squares_x', 5)}")
            c.drawString(right_x, y_start + 5, f"Squares Y: {data.get('squares_y', 7)}")
            c.drawString(
                left_x, y_start + 10, f"Square: {data.get('square_size_mm', 30)}mm"
            )
            c.drawString(
                right_x, y_start + 10, f"Marker: {data.get('marker_size_mm', 30)}mm"
            )
        elif board_type == "checkerboard":
            c.drawString(right_x, y_start, f"Type: Checker")
            c.drawString(left_x, y_start + 5, f"Squares X: {data.get('squares_x', 5)}")
            c.drawString(right_x, y_start + 5, f"Squares Y: {data.get('squares_y', 8)}")
            c.drawString(
                left_x, y_start + 10, f"Square: {data.get('square_size_mm', 30)}mm"
            )
            c.drawString(
                right_x, y_start + 10, f"Border: {data.get('border_mm', 20)}mm"
            )
        else:
            c.drawString(right_x, y_start, f"Dict: {data.get('dictionary')}")
            c.drawString(left_x, y_start + 5, f"Rows: {data.get('rows')}")
            c.drawString(right_x, y_start + 5, f"Cols: {data.get('cols')}")
            c.drawString(left_x, y_start + 10, f"Size: {data.get('marker_size_mm')}mm")
            c.drawString(right_x, y_start + 10, f"Sep: {data.get('separation_mm')}mm")

    c.save()
    buffer.seek(0)
    return buffer


@st.cache_data
def generate_json_config(data: Dict[str, Any]) -> str:
    """Generate a JSON configuration string from grid parameters.

    The JSON contains all settings, computed grid information, and transformation
    data for use by external applications.
    """
    board_type = data.get("board_type", "aruco_grid")

    # Build settings section - base settings
    settings = {
        "board_type": board_type,
        "paper_size": data.get("paper_size", "A4"),
        "orientation": data.get("orientation", "portrait"),
    }

    # Add board type specific settings
    if board_type == "charuco":
        settings.update(
            {
                "dictionary": data.get("dictionary", "DICT_5X5_250"),
                "squares_x": data.get("squares_x", 5),
                "squares_y": data.get("squares_y", 7),
                "square_size_mm": data.get("square_size_mm", 30),
                "marker_size_mm": data.get("marker_size_mm", 30),
                "show_ids": data.get("show_ids", True),
            }
        )
    elif board_type == "checkerboard":
        settings.update(
            {
                "squares_x": data.get("squares_x", 5),
                "squares_y": data.get("squares_y", 8),
                "square_size_mm": data.get("square_size_mm", 30),
                "border_mm": data.get("border_mm", 20),
            }
        )
    else:  # aruco_grid
        settings.update(
            {
                "dictionary": data.get("dictionary", "DICT_5X5_250"),
                "rows": data.get("rows", 5),
                "cols": data.get("cols", 7),
                "marker_size_mm": data.get("marker_size_mm", 30),
                "separation_mm": data.get("separation_mm", 10),
                "show_ids": data.get("show_ids", True),
            }
        )

    settings.update(
        {
            "show_scale": data.get("show_scale", True),
            "show_params": data.get("show_params", True),
            "show_coordsys": data.get("show_coordsys", False),
            "vertical_scale": data.get("vertical_scale", 100.0),
            "horizontal_scale": data.get("horizontal_scale", 100.0),
        }
    )

    # Build grid_info section
    width_mm, height_mm = get_page_dimensions(
        settings["paper_size"], settings["orientation"]
    )

    if board_type == "charuco":
        squares_x = settings.get("squares_x", 5)
        squares_y = settings.get("squares_y", 7)
        square_size_mm = settings.get("square_size_mm", 30)

        total_width_mm = squares_x * square_size_mm
        total_height_mm = squares_y * square_size_mm

        # Calculate corner positions (CharUco has (squares_x-1) * (squares_y-1) corners)
        corner_positions = []
        for row in range(squares_y - 1):
            for col in range(squares_x - 1):
                x_mm = (col + 1) * square_size_mm
                y_mm = (row + 1) * square_size_mm
                corner_positions.append(
                    {
                        "row": row,
                        "col": col,
                        "x_mm": round(x_mm, 2),
                        "y_mm": round(y_mm, 2),
                    }
                )

        grid_info = {
            "page_width_mm": round(width_mm, 2),
            "page_height_mm": round(height_mm, 2),
            "total_board_width_mm": round(total_width_mm, 2),
            "total_board_height_mm": round(total_height_mm, 2),
            "total_corners": (squares_x - 1) * (squares_y - 1),
            "corner_positions_mm": corner_positions,
        }
    elif board_type == "checkerboard":
        squares_x = settings.get("squares_x", 5)
        squares_y = settings.get("squares_y", 8)
        square_size_mm = settings.get("square_size_mm", 30)
        border_mm = settings.get("border_mm", 20)

        total_width_mm = squares_x * square_size_mm + 2 * border_mm
        total_height_mm = squares_y * square_size_mm + 2 * border_mm

        grid_info = {
            "page_width_mm": round(width_mm, 2),
            "page_height_mm": round(height_mm, 2),
            "total_board_width_mm": round(total_width_mm, 2),
            "total_board_height_mm": round(total_height_mm, 2),
            "squares_x": squares_x,
            "squares_y": squares_y,
            "square_size_mm": square_size_mm,
            "border_mm": border_mm,
        }
    else:  # aruco_grid
        marker_size_mm = settings.get("marker_size_mm", 30)
        separation_mm = settings.get("separation_mm", 10)
        rows = settings.get("rows", 5)
        cols = settings.get("cols", 7)

        total_width_mm = cols * marker_size_mm + (cols - 1) * separation_mm
        total_height_mm = rows * marker_size_mm + (rows - 1) * separation_mm

        # Calculate marker positions (center of each marker, from top-left origin)
        offset_x = (width_mm - total_width_mm) / 2
        offset_y = (height_mm - total_height_mm) / 2

        marker_positions = []
        marker_ids = []
        marker_id = 0
        for r in range(rows):
            for c in range(cols):
                x_mm = (
                    offset_x + c * (marker_size_mm + separation_mm) + marker_size_mm / 2
                )
                y_mm = (
                    offset_y + r * (marker_size_mm + separation_mm) + marker_size_mm / 2
                )
                marker_positions.append(
                    {
                        "id": marker_id,
                        "row": r,
                        "col": c,
                        "x_mm": round(x_mm, 2),
                        "y_mm": round(y_mm, 2),
                    }
                )
                marker_ids.append(marker_id)
                marker_id += 1

        grid_info = {
            "page_width_mm": round(width_mm, 2),
            "page_height_mm": round(height_mm, 2),
            "total_grid_width_mm": round(total_width_mm, 2),
            "total_grid_height_mm": round(total_height_mm, 2),
            "total_markers": rows * cols,
            "marker_ids": marker_ids,
            "marker_positions_mm": marker_positions,
        }

    # Build transformation section
    show_coordsys = data.get("show_coordsys", False)
    transformation = {
        "enabled": show_coordsys,
        "base_translation_mm": data.get("base_translation", [0.0, 0.0, 0.0]),
        "base_rotation_deg": data.get("base_rotation", [0.0, 0.0, 0.0]),
    }

    if show_coordsys:
        T, t_m, quat = calculate_transformation(data)
        transformation["matrix_4x4"] = T.tolist()
        transformation["translation_m"] = t_m.tolist()
        transformation["quaternion_xyzw"] = quat.tolist()

    # Assemble final JSON
    config = {
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "settings": settings,
        "grid_info": grid_info,
        "transformation": transformation,
    }

    return json.dumps(config, indent=2)


@st.cache_data
def pdf_to_preview_images(pdf_buffer: io.BytesIO, dpi: int = 150) -> list:
    """Convert PDF buffer to PIL images for preview."""
    pdf_buffer.seek(0)
    images = convert_from_bytes(pdf_buffer.read(), dpi=dpi)
    return images


def _load_image_safe(
    path: str, default_size: Optional[int] = None
) -> Optional[Image.Image]:
    """Safely load an image file with fallback."""
    try:
        if os.path.exists(path):
            return Image.open(path)
    except (OSError, IOError):
        pass
    return None


# Page configuration
st.set_page_config(
    page_title="Calibration Board Generator",
    page_icon=DEFAULT_FAVICON_PATH,
    layout="wide",
)

# Load external CSS
css_path = "static/style.css"
if os.path.exists(css_path):
    with open(css_path, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Initialize session state for persistent preview
if "last_valid_preview" not in st.session_state:
    st.session_state.last_valid_preview = None
if "last_valid_pdf" not in st.session_state:
    st.session_state.last_valid_pdf = None
if "last_settings_hash" not in st.session_state:
    st.session_state.last_settings_hash = None
if "toast_message" not in st.session_state:
    st.session_state.toast_message = None
if "show_toast" not in st.session_state:
    st.session_state.show_toast = False


# Function to generate dummy preview from default settings
@st.cache_data
def generate_dummy_preview(board_type: str = "aruco_grid") -> Image.Image:
    """Generate a preview image using default settings for placeholder."""
    if board_type == "charuco":
        default_data = {
            "board_type": "charuco",
            "paper_size": "A4",
            "orientation": "portrait",
            "dictionary": "DICT_5X5_250",
            "squares_x": 5,
            "squares_y": 7,
            "square_size_mm": 30,
            "marker_size_mm": 18,
            "show_ids": False,
            "show_scale": True,
            "show_params": True,
            "vertical_scale": 100.0,
            "horizontal_scale": 100.0,
        }
        return generate_charuco_board(default_data, low_res=True, draw_overlays=True)
    elif board_type == "checkerboard":
        default_data = {
            "board_type": "checkerboard",
            "paper_size": "A4",
            "orientation": "portrait",
            "squares_x": 5,
            "squares_y": 8,
            "square_size_mm": 30,
            "border_mm": 20,
            "show_scale": True,
            "show_params": True,
            "vertical_scale": 100.0,
            "horizontal_scale": 100.0,
        }
        return generate_checkerboard(default_data, low_res=True, draw_overlays=True)
    else:
        default_data = DEFAULT_SETTINGS.copy()
        default_data["board_type"] = "aruco_grid"
        return generate_aruco_grid(default_data, low_res=True, draw_overlays=True)


st.markdown(
    "<h1 style='text-align: center;'>Calibration Board Generator</h1>",
    unsafe_allow_html=True,
)

# Sidebar for configuration
with st.sidebar:
    match_logo = _load_image_safe(DEFAULT_LOGO_PATH, 60)
    if match_logo:
        st.image(match_logo, width="stretch")

    st.header("Configuration")

    # Board type selector
    board_type = st.radio(
        "Board Type",
        ["ArUco Grid", "CharUco Board", "Checkerboard"],
        index=0,
        help="Select the type of calibration board to generate",
    )

    # Convert to internal type
    board_type_internal = (
        "aruco_grid"
        if board_type == "ArUco Grid"
        else ("charuco" if board_type == "CharUco Board" else "checkerboard")
    )

    with st.expander("Page and Layout", expanded=True):
        paper_size = st.selectbox(
            "Paper Size",
            ["A4", "A3", "A2", "A1", "Letter", "Legal"],
            index=0,
        )
        orientation = st.selectbox("Orientation", ["portrait", "landscape"], index=0)

    # Show board-specific parameters based on type
    if board_type == "CharUco Board":
        with st.expander("CharUco Board Settings", expanded=True):
            dictionary = st.selectbox(
                "ArUco Dictionary",
                [
                    "DICT_4X4_50",
                    "DICT_4X4_100",
                    "DICT_4X4_250",
                    "DICT_4X4_1000",
                    "DICT_5X5_50",
                    "DICT_5X5_100",
                    "DICT_5X5_250",
                    "DICT_5X5_1000",
                    "DICT_6X6_50",
                    "DICT_6X6_100",
                    "DICT_6X6_250",
                    "DICT_6X6_1000",
                    "DICT_7X7_50",
                    "DICT_7X7_100",
                    "DICT_7X7_250",
                    "DICT_7X7_1000",
                ],
                index=6,
                help="ArUco dictionary for CharUco markers",
            )
            squares_x = st.number_input(
                "Squares X",
                min_value=2,
                max_value=MAX_GRID_SIZE,
                value=5,
                step=1,
                help="Number of squares in X direction",
            )
            squares_y = st.number_input(
                "Squares Y",
                min_value=2,
                max_value=MAX_GRID_SIZE,
                value=7,
                step=1,
                help="Number of squares in Y direction",
            )
            square_size_mm = st.number_input(
                "Square Size (mm)",
                min_value=1,
                max_value=MAX_MARKER_SIZE,
                value=30,
                step=1,
            )
            marker_size_mm = st.number_input(
                "Marker Size (mm)",
                min_value=1,
                max_value=MAX_MARKER_SIZE,
                value=18,
                step=1,
                help="Size of ArUco markers (recommended: 50-70% of square size for proper separation)",
            )
            show_ids = st.checkbox(
                "Show Marker IDs",
                value=False,
                help="Show ArUco marker IDs on the board",
            )

    elif board_type == "Checkerboard":
        with st.expander("Checkerboard Settings", expanded=True):
            squares_x = st.number_input(
                "Squares X",
                min_value=2,
                max_value=MAX_GRID_SIZE,
                value=5,
                step=1,
                help="Number of squares in X direction",
            )
            squares_y = st.number_input(
                "Squares Y",
                min_value=2,
                max_value=MAX_GRID_SIZE,
                value=8,
                step=1,
                help="Number of squares in Y direction",
            )
            square_size_mm = st.number_input(
                "Square Size (mm)",
                min_value=1,
                max_value=MAX_MARKER_SIZE,
                value=30,
                step=1,
            )
            border_mm = st.number_input(
                "Border (mm)",
                min_value=0,
                max_value=100,
                value=20,
                step=1,
                help="White border around the checkerboard",
            )
            show_ids = False  # Checkerboard doesn't have IDs

    else:  # ArUco Grid (default)
        with st.expander("ArUco Grid Settings", expanded=True):
            dictionary = st.selectbox(
                "ArUco Dictionary",
                [
                    "DICT_4X4_50",
                    "DICT_4X4_100",
                    "DICT_4X4_250",
                    "DICT_4X4_1000",
                    "DICT_5X5_50",
                    "DICT_5X5_100",
                    "DICT_5X5_250",
                    "DICT_5X5_1000",
                    "DICT_6X6_50",
                    "DICT_6X6_100",
                    "DICT_6X6_250",
                    "DICT_6X6_1000",
                    "DICT_7X7_50",
                    "DICT_7X7_100",
                    "DICT_7X7_250",
                    "DICT_7X7_1000",
                    "DICT_ARUCO_ORIGINAL",
                    "DICT_APRILTAG_16h5",
                    "DICT_APRILTAG_25h9",
                    "DICT_APRILTAG_36h10",
                    "DICT_APRILTAG_36h11",
                    "DICT_ARUCO_MIP_36h12",
                ],
                index=5,
            )

        with st.expander("Grid Dimensions", expanded=True):
            cols = st.number_input(
                "Columns", min_value=1, max_value=MAX_GRID_SIZE, value=5, step=1
            )
            rows = st.number_input(
                "Rows", min_value=1, max_value=MAX_GRID_SIZE, value=7, step=1
            )
            marker_size_mm = st.number_input(
                "Marker Size (mm)",
                min_value=1,
                max_value=MAX_MARKER_SIZE,
                value=30,
                step=1,
            )
            separation_mm = st.number_input(
                "Separation (mm)", min_value=1, value=10, step=1
            )

    # Common elements for all board types - Optional Information
    with st.expander("Optional Information", expanded=False):
        # Show Marker IDs option only for ArUco Grid
        if board_type == "ArUco Grid":
            show_ids = st.checkbox("Marker IDs", value=True)

            marker_id_font_size = None
            if show_ids:
                col_font, _ = st.columns([3, 2])
                with col_font:
                    marker_id_font_size = st.number_input(
                        "ID Font Size",
                        min_value=6,
                        max_value=72,
                        value=24,
                        step=1,
                        help="Font size for marker ID labels (in pixels at 300 DPI)",
                    )
        else:
            show_ids = False
            marker_id_font_size = None

        show_scale = st.checkbox("Scale Ruler", value=True)
        show_params = st.checkbox("Parameters", value=True)
        if board_type == "ArUco Grid":
            show_coordsys = st.checkbox("Coordinate System", value=False)
        else:
            show_coordsys = False
        col1, col2 = st.columns(2)
        with col1:
            horizontal_scale = st.number_input(
                "Horizontal Scale (%)",
                min_value=0.1,
                max_value=200.0,
                value=100.0,
                step=0.1,
                format="%.1f",
            )
        with col2:
            vertical_scale = st.number_input(
                "Vertical Scale (%)",
                min_value=0.1,
                max_value=200.0,
                value=100.0,
                step=0.1,
                format="%.1f",
            )

    base_translation_x = 0.0
    base_translation_y = 0.0
    base_translation_z = 0.0
    base_rotation_roll = 0.0
    base_rotation_pitch = 0.0
    base_rotation_yaw = 0.0

    # Only show coordinate system for ArUco Grid
    if show_coordsys and board_type == "ArUco Grid":
        with st.expander("Coordinate System", expanded=True):
            base_translation_x = st.number_input(
                "Translation X (mm)", value=0.0, step=0.1
            )
            base_translation_y = st.number_input(
                "Translation Y (mm)", value=0.0, step=0.1
            )
            base_translation_z = st.number_input(
                "Translation Z (mm)", value=0.0, step=0.1
            )
            base_rotation_roll = st.number_input("Roll (deg)", value=0.0, step=0.1)
            base_rotation_pitch = st.number_input("Pitch (deg)", value=0.0, step=0.1)
            base_rotation_yaw = st.number_input("Yaw (deg)", value=0.0, step=0.1)

            data_for_calc = {
                "paper_size": paper_size,
                "orientation": orientation,
                "base_translation": [
                    base_translation_x,
                    base_translation_y,
                    base_translation_z,
                ],
                "base_rotation": [
                    base_rotation_roll,
                    base_rotation_pitch,
                    base_rotation_yaw,
                ],
            }
            T, t_m, quat = calculate_transformation(data_for_calc)

            st.caption("Transformation")
            st.code(
                f"T = [[{T[0, 0]:.2f}, {T[0, 1]:.2f}, {T[0, 2]:.2f}, {T[0, 3]:.2f}],\n"
                f"[{T[1, 0]:.2f}, {T[1, 1]:.2f}, {T[1, 2]:.2f}, {T[1, 3]:.2f}],\n"
                f"[{T[2, 0]:.2f}, {T[2, 1]:.2f}, {T[2, 2]:.2f}, {T[2, 3]:.2f}]]"
            )
            st.code(f"t = [{t_m[0]:.4f}, {t_m[1]:.4f}, {t_m[2]:.4f}]")
            st.code(f"q = [{quat[0]:.4f}, {quat[1]:.4f}, {quat[2]:.4f}, {quat[3]:.4f}]")

data = {
    "board_type": board_type_internal,
    "paper_size": paper_size,
    "orientation": orientation,
}

# Add board-type-specific parameters
if board_type == "CharUco Board":
    data.update(
        {
            "dictionary": dictionary,
            "squares_x": squares_x,
            "squares_y": squares_y,
            "square_size_mm": square_size_mm,
            "marker_size_mm": marker_size_mm,
            "show_ids": show_ids,
        }
    )
elif board_type == "Checkerboard":
    data.update(
        {
            "squares_x": squares_x,
            "squares_y": squares_y,
            "square_size_mm": square_size_mm,
            "border_mm": border_mm,
        }
    )
else:  # ArUco Grid
    data.update(
        {
            "dictionary": dictionary,
            "rows": rows,
            "cols": cols,
            "marker_size_mm": marker_size_mm,
            "separation_mm": separation_mm,
            "show_ids": show_ids,
            "marker_id_font_size": marker_id_font_size,
        }
    )

data.update(
    {
        "show_scale": show_scale,
        "show_params": show_params,
        "show_coordsys": show_coordsys,
        "vertical_scale": vertical_scale,
        "horizontal_scale": horizontal_scale,
    }
)

if show_coordsys and board_type == "ArUco Grid":
    data["base_translation"] = [
        base_translation_x,
        base_translation_y,
        base_translation_z,
    ]
    data["base_rotation"] = [base_rotation_roll, base_rotation_pitch, base_rotation_yaw]

# Compute settings hash to detect changes
current_hash = get_settings_hash(data)

# Check if settings changed - if so, we'll keep showing old preview during generation
settings_changed = st.session_state.last_settings_hash != current_hash

# Generate PDF and preview
current_error = None
preview_images = None
pdf_buffer = None

try:
    pdf_buffer = generate_pdf(data)
    preview_images = pdf_to_preview_images(pdf_buffer, dpi=150)

    # Store successful preview in session state
    st.session_state.last_valid_preview = preview_images[0] if preview_images else None
    st.session_state.last_valid_pdf = pdf_buffer
    st.session_state.last_settings_hash = current_hash

    # Clear any previous toast
    st.session_state.show_toast = False
    st.session_state.toast_message = None

except ValueError as e:
    # Store error for toast display, but keep showing previous preview
    current_error = str(e)
    st.session_state.toast_message = current_error
    st.session_state.show_toast = True
    # Keep using last valid preview and PDF
    preview_images = (
        [st.session_state.last_valid_preview]
        if st.session_state.last_valid_preview
        else None
    )
    pdf_buffer = st.session_state.last_valid_pdf

# Determine which preview to show
display_preview = None
if preview_images and preview_images[0] is not None:
    display_preview = preview_images[0]
elif st.session_state.last_valid_preview is not None:
    display_preview = st.session_state.last_valid_preview
else:
    # Generate dummy preview for first load
    display_preview = generate_dummy_preview(board_type_internal)

# Determine if we should show blur effect (during generation or on error)
show_blur = settings_changed or (current_error is not None)

# Build the preview display with optional toast
if display_preview is not None:
    # Convert PIL Image to base64 for HTML display
    import base64
    from io import BytesIO

    img_buffer = BytesIO()
    display_preview.save(img_buffer, format="PNG")
    img_base64 = base64.b64encode(img_buffer.getvalue()).decode()

    # Build toast HTML if there's an error
    toast_html = ""
    if st.session_state.show_toast and st.session_state.toast_message:
        toast_html = f"""
        <div class="toast-overlay">
            <span class="toast-icon">⚠️</span>
            <span class="toast-message">{st.session_state.toast_message}</span>
        </div>
        """

    # Render preview with HTML
    st.markdown(
        f"""
        <div class="preview-container">
            <img src="data:image/png;base64,{img_base64}" 
                 alt="ArUco Grid Preview">
            {toast_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

if pdf_buffer is not None:
    # Determine filename based on board type
    if board_type == "CharUco Board":
        pdf_filename = "charuco_board.pdf"
        json_filename = "charuco_board_config.json"
    elif board_type == "Checkerboard":
        pdf_filename = "checkerboard.pdf"
        json_filename = "checkerboard_config.json"
    else:
        pdf_filename = "aruco_grid.pdf"
        json_filename = "aruco_grid_config.json"

    # Use empty columns on the sides to squeeze the middle column
    # [3, 2, 3] usually creates a nice medium-sized button
    col1, col2, col3 = st.columns([4, 1, 4])

    with col2:
        st.download_button(
            label="**Download PDF**",
            data=pdf_buffer,
            file_name=pdf_filename,
            mime="application/pdf",
            type="primary",
            width="stretch",  # This fills the (now smaller) middle column
        )

    # Add JSON download button
    json_config = generate_json_config(data)
    col1, col2, col3 = st.columns([4, 1, 4])

    with col2:
        st.download_button(
            label="Download JSON",
            data=json_config,
            file_name=json_filename,
            mime="application/json",
            type="secondary",
            width="stretch",
        )
