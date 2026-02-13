"""
ArUco Grid Generator - Streamlit Version

A web application for generating printable ArUco marker grids for computer vision and robotics.
"""

import hashlib
import io
import math
import os
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
    """Generate a PDF file with the ArUco grid."""
    show_scale = data.get("show_scale", True)
    show_params = data.get("show_params", True)

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
        c.drawString(right_x, y_start, f"Dict: {data.get('dictionary')}")
        c.drawString(left_x, y_start + 5, f"Rows: {data.get('rows')}")
        c.drawString(right_x, y_start + 5, f"Cols: {data.get('cols')}")
        c.drawString(left_x, y_start + 10, f"Size: {data.get('marker_size_mm')}mm")
        c.drawString(right_x, y_start + 10, f"Sep: {data.get('separation_mm')}mm")

    c.save()
    buffer.seek(0)
    return buffer


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
    page_title="ArUco Grid Generator",
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
def generate_dummy_preview() -> Image.Image:
    """Generate a preview image using default settings for placeholder."""
    default_data = DEFAULT_SETTINGS.copy()
    return generate_aruco_grid(default_data, low_res=True, draw_overlays=True)


st.title("ArUco Grid Generator")

# Sidebar for configuration
with st.sidebar:
    match_logo = _load_image_safe(DEFAULT_LOGO_PATH, 60)
    if match_logo:
        st.image(match_logo, width="stretch")

    st.header("Configuration")

    with st.expander("Page and Layout", expanded=True):
        paper_size = st.selectbox(
            "Paper Size",
            ["A4", "A3", "A2", "A1", "Letter", "Legal"],
            index=0,
        )
        orientation = st.selectbox("Orientation", ["portrait", "landscape"], index=0)
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
            "Marker Size (mm)", min_value=1, max_value=MAX_MARKER_SIZE, value=30, step=1
        )
        separation_mm = st.number_input(
            "Separation (mm)", min_value=1, value=10, step=1
        )

    with st.expander("Optional Information", expanded=False):
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

        show_scale = st.checkbox("Scale Ruler", value=True)
        show_params = st.checkbox("Parameters", value=True)
        show_coordsys = st.checkbox("Coordinate System", value=False)
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

    if show_coordsys:
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
    "paper_size": paper_size,
    "orientation": orientation,
    "dictionary": dictionary,
    "rows": rows,
    "cols": cols,
    "marker_size_mm": marker_size_mm,
    "separation_mm": separation_mm,
    "show_ids": show_ids,
    "show_scale": show_scale,
    "show_params": show_params,
    "show_coordsys": show_coordsys,
    "vertical_scale": vertical_scale,
    "horizontal_scale": horizontal_scale,
    "marker_id_font_size": marker_id_font_size,
}

if show_coordsys:
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
    display_preview = generate_dummy_preview()

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
    # Use empty columns on the sides to squeeze the middle column
    # [3, 2, 3] usually creates a nice medium-sized button
    col1, col2, col3 = st.columns([4, 1, 4])

    with col2:
        st.download_button(
            label="**Download PDF**",
            data=pdf_buffer,
            file_name="aruco_grid.pdf",
            mime="application/pdf",
            type="primary",
            width="stretch",  # This fills the (now smaller) middle column
        )


st.markdown(
    """
    <div style="text-align: center;">
        ArUco Grid Generator - Generated with Streamlit
    </div>
    """,
    unsafe_allow_html=True,
)

# Removed st.rerun() - it was causing infinite refresh loop in Docker
