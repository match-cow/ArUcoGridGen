import io
import math

import cv2
import numpy as np
from flask import Flask, jsonify, render_template, request, send_file
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A3, A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from scipy.spatial.transform import Rotation as R_scipy


def generate_aruco_grid(data, low_res=False, draw_overlays=True):
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

    # Paper dimensions in mm
    if paper_size == "A4":
        if orientation == "portrait":
            width_mm, height_mm = 210, 297
        else:
            width_mm, height_mm = 297, 210
    else:  # A3
        if orientation == "portrait":
            width_mm, height_mm = 297, 420
        else:
            width_mm, height_mm = 420, 297

    # Calculate total grid size
    total_width_mm = cols * marker_size_mm + (cols - 1) * separation_mm
    total_height_mm = rows * marker_size_mm + (rows - 1) * separation_mm

    # Auto-resize if needed
    scale = 1.0
    if total_width_mm > width_mm or total_height_mm > height_mm:
        scale = min(width_mm / total_width_mm, height_mm / total_height_mm)
        marker_size_mm *= scale
        separation_mm *= scale
        total_width_mm *= scale
        total_height_mm *= scale

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
        except:
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
            except:
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
        except:
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

    return pil_img


def calculate_transformation(data):
    paper_size = data.get("paper_size", "A4")
    orientation = data.get("orientation", "portrait")
    base_translation = data.get("base_translation", [0, 0, 0])
    base_rotation = data.get("base_rotation", [0, 0, 0])  # roll, pitch, yaw in degrees

    # Paper dimensions in mm
    if paper_size == "A4":
        width_mm, height_mm = (210, 297) if orientation == "portrait" else (297, 210)
    else:  # A3
        width_mm, height_mm = (297, 420) if orientation == "portrait" else (420, 297)

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
    # Extract parameters
    show_ids = data.get("show_ids", True)
    show_scale = data.get("show_scale", True)
    show_coordsys = data.get("show_coordsys", False)
    show_params = data.get("show_params", True)

    # Generate high-res image
    img = generate_aruco_grid(data, low_res=False, draw_overlays=False)

    # Paper size
    paper_size = data.get("paper_size", "A4")
    orientation = data.get("orientation", "portrait")
    if paper_size == "A4":
        pagesize = A4 if orientation == "portrait" else (A4[1], A4[0])
    else:
        pagesize = A3 if orientation == "portrait" else (A3[1], A3[0])

    # Create PDF
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=pagesize)

    width, height = pagesize

    # Draw the image
    c.drawInlineImage(img, 0, 0, width=width, height=height)

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


app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/preview", methods=["POST"])
def preview():
    data = request.get_json()
    # Generate low-res preview
    img = generate_aruco_grid(data, low_res=True)
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    return send_file(img_bytes, mimetype="image/png")


@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json()
    pdf_buffer = generate_pdf(data)
    return send_file(pdf_buffer, mimetype="application/pdf")


if __name__ == "__main__":
    app.run(debug=True)
