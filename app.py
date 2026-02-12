"""
ArUco Grid Generator - Streamlit Version

A web application for generating printable ArUco marker grids for computer vision and robotics.
"""

import io
import math

import cv2
import numpy as np
import streamlit as st
from pdf2image import convert_from_bytes
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A3, A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from scipy.spatial.transform import Rotation as R_scipy

# Constants
PT_TO_MM = 25.4 / 72  # Convert points to mm (72 points per inch)


def get_page_dimensions(paper_size, orientation):
    """Get page dimensions in mm using reportlab pagesizes."""
    if paper_size == "A4":
        pagesize = A4
    else:  # A3
        pagesize = A3

    width_pt, height_pt = pagesize
    width_mm = width_pt * PT_TO_MM
    height_mm = height_pt * PT_TO_MM

    if orientation == "portrait":
        return width_mm, height_mm
    else:  # landscape
        return height_mm, width_mm


def get_pagesize(paper_size, orientation):
    """Get page dimensions in points for reportlab PDF generation."""
    if paper_size == "A4":
        pagesize = A4
    else:  # A3
        pagesize = A3

    if orientation == "portrait":
        return pagesize
    else:  # landscape
        return (pagesize[1], pagesize[0])


def generate_aruco_grid(data, low_res=False, draw_overlays=True):
    """Generate an ArUco grid image based on the provided parameters."""
    # Extract parameters
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

    # Get dictionary
    aruco_dict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dictionary_name))

    # Validate grid size against dictionary capacity
    max_markers = 250  # All standard ArUco dictionaries have 250 markers
    total_markers = rows * cols
    if total_markers > max_markers:
        raise ValueError(
            f"Grid size ({rows}×{cols}={total_markers}) exceeds dictionary capacity ({max_markers}). "
            f"Please reduce rows or columns."
        )

    # Paper dimensions in mm
    width_mm, height_mm = get_page_dimensions(paper_size, orientation)

    # Calculate total grid size
    total_width_mm = cols * marker_size_mm + (cols - 1) * separation_mm
    total_height_mm = rows * marker_size_mm + (rows - 1) * separation_mm

    # Validate that grid fits on page
    if total_width_mm > width_mm or total_height_mm > height_mm:
        raise ValueError(
            f"Grid size ({total_width_mm:.1f}mm × {total_height_mm:.1f}mm) exceeds "
            f"page size ({width_mm:.1f}mm × {height_mm:.1f}mm). "
            f"Please reduce marker size, separation, rows, or columns, or use larger paper."
        )

    # For preview, use low resolution
    dpi = 72 if low_res else 300
    px_per_mm = dpi / 25.4  # pixels per mm

    marker_size_px = int(marker_size_mm * px_per_mm)
    separation_px = int(separation_mm * px_per_mm)

    # Calculate total grid size in pixels
    total_width_px = cols * marker_size_px + (cols - 1) * separation_px
    total_height_px = rows * marker_size_px + (rows - 1) * separation_px

    # Create blank image of page size
    img_width_px = int(width_mm * px_per_mm)
    img_height_px = int(height_mm * px_per_mm)
    img = (
        np.ones((img_height_px, img_width_px, 3), dtype=np.uint8) * 255
    )  # white background

    # Calculate offset to center the grid
    offset_x = (img_width_px - total_width_px) // 2
    offset_y = (img_height_px - total_height_px) // 2

    # Generate and place markers centered
    marker_id = 0
    for r in range(rows):
        for c in range(cols):
            # Generate marker
            marker_img = cv2.aruco.generateImageMarker(
                aruco_dict, marker_id, marker_size_px
            )
            marker_img = cv2.cvtColor(marker_img, cv2.COLOR_GRAY2BGR)

            # Position centered
            x = offset_x + c * (marker_size_px + separation_px)
            y = offset_y + r * (marker_size_px + separation_px)

            # Place on image
            img[y : y + marker_size_px, x : x + marker_size_px] = marker_img

            marker_id += 1

    # Convert to PIL Image
    pil_img = Image.fromarray(img)

    # Add IDs if show_ids
    if show_ids:
        draw = ImageDraw.Draw(pil_img)
        font_size = (
            min(12, marker_size_px // 7) if low_res else min(24, marker_size_px // 7)
        )
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()
        marker_id = 0
        for r in range(rows):
            for c in range(cols):
                # Place ID below the marker, centered
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
        # Add scale if show_scale
        if show_scale:
            draw = ImageDraw.Draw(pil_img)
            # Draw 10 cm ruler at bottom left
            ruler_y = img_height_px - 20
            ruler_length_px = 100 * px_per_mm  # 10 cm
            start_x = 10  # small margin
            for i in range(0, 101, 1):  # 0 to 100 mm
                x = start_x + i * px_per_mm
                if i % 10 == 0:  # cm tick
                    draw.line(
                        (x, ruler_y, x, ruler_y + 15), fill=(128, 128, 128), width=1
                    )
                else:  # mm tick
                    draw.line(
                        (x, ruler_y, x, ruler_y + 8), fill=(128, 128, 128), width=1
                    )
            # Add "10 cm" label
            draw.text(
                (start_x + ruler_length_px + 5, ruler_y - 5),
                "10 cm",
                fill=(128, 128, 128),
            )

        # If show_params, draw parameters at bottom right
        if data.get("show_params", True):
            font_size = 6
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except OSError:
                font = ImageFont.load_default()
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

    # Draw coordinate system if enabled (only when drawing overlays)
    if show_coordsys and draw_overlays:
        draw = ImageDraw.Draw(pil_img)
        cx = img_width_px // 2
        cy = img_height_px // 2
        axis_length = 50  # pixels
        font_size = 12
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()
        # X axis (red, horizontal)
        draw.line(
            (cx - axis_length, cy, cx + axis_length, cy), fill=(255, 0, 0), width=2
        )
        # Arrow head for X
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
        # Label X
        draw.text((cx + axis_length + 5, cy - 10), "X", fill=(255, 0, 0), font=font)
        # Y axis (green, vertical)
        draw.line(
            (cx, cy - axis_length, cx, cy + axis_length), fill=(0, 255, 0), width=2
        )
        # Arrow head for Y
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
        # Label Y
        draw.text((cx + 5, cy - axis_length - 15), "Y", fill=(0, 255, 0), font=font)

    # Draw solid grey border for preview
    if low_res:
        draw = ImageDraw.Draw(pil_img)
        width, height = pil_img.size
        grey = (128, 128, 128)
        # Top
        draw.line((0, 0, width - 1, 0), fill=grey, width=2)
        # Bottom
        draw.line((0, height - 1, width - 1, height - 1), fill=grey, width=2)
        # Left
        draw.line((0, 0, 0, height - 1), fill=grey, width=2)
        # Right
        draw.line((width - 1, 0, width - 1, height - 1), fill=grey, width=2)

    # Apply vertical/horizontal scaling if not 100%
    vertical_scale = data.get("vertical_scale", 100.0) / 100.0
    horizontal_scale = data.get("horizontal_scale", 100.0) / 100.0

    if vertical_scale != 1.0 or horizontal_scale != 1.0:
        new_width = int(pil_img.width * horizontal_scale)
        new_height = int(pil_img.height * vertical_scale)
        pil_img = pil_img.resize((new_width, new_height), Image.LANCZOS)

    return pil_img


def calculate_transformation(data):
    """Calculate transformation matrix from grid parameters."""
    paper_size = data.get("paper_size", "A4")
    orientation = data.get("orientation", "portrait")
    base_translation = data.get("base_translation", [0, 0, 0])
    base_rotation = data.get("base_rotation", [0, 0, 0])  # roll, pitch, yaw in degrees

    # Paper dimensions in mm
    width_mm, height_mm = get_page_dimensions(paper_size, orientation)

    tx, ty, tz = base_translation
    roll, pitch, yaw = [math.radians(r) for r in base_rotation]

    # Default R: 180 around X
    R_default = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]])

    # User rotation
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

    # Homogeneous transformation matrix
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = t

    # Translation in meters
    t_m = t / 1000

    # Quaternion from R
    r = R_scipy.from_matrix(R)
    quat = r.as_quat()  # [x,y,z,w]

    return T, t_m, quat


def generate_pdf(data):
    """Generate a PDF file with the ArUco grid."""
    # Extract parameters (unused but kept for consistency with data structure)
    _ = data.get("show_ids", True)
    show_scale = data.get("show_scale", True)
    _ = data.get("show_coordsys", False)
    show_params = data.get("show_params", True)

    # Generate high-res image (already scaled based on vertical_scale/horizontal_scale)
    img = generate_aruco_grid(data, low_res=False, draw_overlays=False)

    # Paper size
    paper_size = data.get("paper_size", "A4")
    orientation = data.get("orientation", "portrait")
    pagesize = get_pagesize(paper_size, orientation)

    # Create PDF
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=pagesize)

    width, height = pagesize

    # Get image dimensions in points
    img_width, img_height = img.size
    pt_per_px = 72.0 / 300  # Convert pixels to points (image is 300 DPI)
    img_width_pt = img_width * pt_per_px
    img_height_pt = img_height * pt_per_px

    # Draw the image centered on the page (user's scale is preserved)
    x_offset = (width - img_width_pt) / 2
    y_offset = (height - img_height_pt) / 2
    c.drawInlineImage(img, x_offset, y_offset, width=img_width_pt, height=img_height_pt)

    # If show_scale, draw ruler
    if show_scale:
        # Draw 10 cm ruler at bottom left
        c.setFont("Helvetica", 8)
        c.setStrokeColorRGB(0.5, 0.5, 0.5)  # grey
        c.setFillColorRGB(0.5, 0.5, 0.5)
        start_x = 20
        ruler_y = 20
        for i in range(0, 101, 1):  # 0 to 100 mm
            x = start_x + i * mm
            if i % 10 == 0:  # cm tick
                c.line(x, ruler_y, x, ruler_y + 8)
            else:  # mm tick
                c.line(x, ruler_y, x, ruler_y + 4)
        # Add "10 cm" label
        c.drawString(start_x + 100 * mm + 5, ruler_y, "10 cm")

    # If show_params, draw parameters
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

    # Calculate transformation (not displayed on PDF)
    T, t_m, quat = calculate_transformation(data)

    c.save()
    buffer.seek(0)
    return buffer


def pdf_to_preview_images(pdf_buffer, dpi=150):
    """Convert PDF buffer to PIL images for preview."""
    pdf_buffer.seek(0)
    images = convert_from_bytes(pdf_buffer.read(), dpi=dpi)
    return images


# -----------------------------------------------------------------------------

# Page configuration
st.set_page_config(
    page_title="ArUco Grid Generator",
    page_icon="static/matchfavicon.png",
    layout="wide",
)

# Main title
st.title("ArUco Grid Generator")

# Sidebar for configuration
with st.sidebar:
    # Load branding logo
    match_logo = Image.open("static/match.png")
    st.image(match_logo, width=60)

    st.header("Configuration")

    # Paper Settings Section
    with st.expander("Page and Layout", expanded=True):
        paper_size = st.selectbox("Paper Size", ["A4", "A3"], index=0)
        orientation = st.selectbox("Orientation", ["portrait", "landscape"], index=0)
        dictionary = st.selectbox(
            "ArUco Dictionary",
            [
                "DICT_4X4_250",
                "DICT_5X5_250",
                "DICT_6X6_250",
                "DICT_7X7_250",
                "DICT_ARUCO_ORIGINAL",
            ],
            index=1,
        )

    # Grid Dimensions Section
    with st.expander("Grid Dimensions", expanded=True):
        cols = st.number_input("Columns", min_value=1, value=5, step=1)
        rows = st.number_input("Rows", min_value=1, value=7, step=1)
        marker_size_mm = st.number_input(
            "Marker Size (mm)", min_value=1, value=30, step=1
        )
        separation_mm = st.number_input(
            "Separation (mm)", min_value=1, value=10, step=1
        )

    # Display Options Section
    with st.expander("Optional Information", expanded=False):
        show_ids = st.checkbox("Marker IDs", value=True)
        show_scale = st.checkbox("Scale Ruler", value=True)
        show_params = st.checkbox("Parameters", value=True)
        show_coordsys = st.checkbox("Coordinate System", value=False)
        col1, col2 = st.columns(2)
        with col1:
            horizontal_scale = st.number_input(
                "Horizontal Scale (%)",
                min_value=0.1,
                value=100.0,
                step=0.1,
                format="%.1f",
            )
        with col2:
            vertical_scale = st.number_input(
                "Vertical Scale (%)",
                min_value=0.1,
                value=100.0,
                step=0.1,
                format="%.1f",
            )

    # Coordinate System Section (conditionally visible)
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

            # Calculate and display transformation info
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
                f"T = [[{T[0, 0]:.2f}, {T[0, 1]:.2f}, {T[0, 2]:.2f}, {T[0, 3]:.2f}],\n[{T[1, 0]:.2f}, {T[1, 1]:.2f}, {T[1, 2]:.2f}, {T[1, 3]:.2f}],\n[{T[2, 0]:.2f}, {T[2, 1]:.2f}, {T[2, 2]:.2f}, {T[2, 3]:.2f}]]"
            )
            st.code(f"t = [{t_m[0]:.4f}, {t_m[1]:.4f}, {t_m[2]:.4f}]")
            st.code(f"q = [{quat[0]:.4f}, {quat[1]:.4f}, {quat[2]:.4f}, {quat[3]:.4f}]")
    else:
        base_translation_x = 0.0
        base_translation_y = 0.0
        base_translation_z = 0.0
        base_rotation_roll = 0.0
        base_rotation_pitch = 0.0
        base_rotation_yaw = 0.0

# Build data dictionary from inputs
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
    "base_translation": [base_translation_x, base_translation_y, base_translation_z],
    "base_rotation": [base_rotation_roll, base_rotation_pitch, base_rotation_yaw],
}

# Main content area

# CSS for responsive preview that fits in window and accent color
st.markdown(
    """
    <style>
    /* Set primary/accent color */
    :root {
        --primary-color: #b1cb21;
        --secondary-color: #9eb81c;
    }
    
    /* Primary button styling */
    .stButton > button[data-testid="baseButton-primary"] {
        background-color: #b1cb21 !important;
        border-color: #b1cb21 !important;
        color: white !important;
    }
    .stButton > button[data-testid="baseButton-primary"]:hover {
        background-color: #9eb81c !important;
        border-color: #9eb81c !important;
        color: white !important;
    }
    
    /* Input field focus borders */
    .stTextInput > div > div:focus-within,
    .stNumberInput > div > div:focus-within,
    .stSelectbox > div > div:focus-within {
        border-color: #b1cb21 !important;
        box-shadow: 0 0 0 1px #b1cb21 !important;
    }
    
    /* Checkbox accent color */
    .stCheckbox > label > div[data-testid="stMarkdownContainer"] > p,
    .stCheckbox svg[data-testid="stCheckboxSvg"] {
        color: #b1cb21;
    }
    .stCheckbox svg[data-testid="stCheckboxSvg"] {
        color: #b1cb21;
    }
    .stCheckbox input:checked + svg {
        background-color: #b1cb21;
        border-color: #b1cb21;
    }
    
    /* Expander header hover */
    .streamlit-expanderHeader:hover {
        background-color: rgba(177, 203, 33, 0.1) !important;
    }
    
    /* Divider color */
    hr {
        border-color: #b1cb21 !important;
    }
    
    /* Code block border */
    .stCodeBlock {
        border-left-color: #b1cb21 !important;
    }
    
    div.stImage {
        max-height: 65vh !important;
        overflow: hidden;
    }
    div.stImage img {
        max-height: 65vh;
        object-fit: contain;
        width: 100% !important;
        height: auto !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Generate PDF and preview
with st.spinner("Generating PDF..."):
    try:
        pdf_buffer = generate_pdf(data)
        preview_images = pdf_to_preview_images(pdf_buffer, dpi=150)
    except ValueError as e:
        st.error(str(e))
        st.stop()

if preview_images:
    st.image(
        preview_images[0], caption="Live Preview - ArUco Grid (PDF)", width="stretch"
    )

st.download_button(
    label="Download PDF",
    data=pdf_buffer,
    file_name="aruco_grid.pdf",
    mime="application/pdf",
    type="primary",
)

# Footer
st.markdown(
    """
    <div style="text-align: center;">
        ArUco Grid Generator - Generated with Streamlit 
        <a href="https://www.match.uni-hannover.de" style="color: rgb(177, 203, 33);" target="_blank"> at match</a> 
    </div>
    """,
    unsafe_allow_html=True,
)
