# Streamlit Migration Plan for ArUco Grid Generator

## Overview

**Goal**: Migrate the existing Flask-based ArUco Grid Generator to Streamlit for improved maintainability, faster development, and more consistent UI design.

**Current Stack**: Flask + HTML + Tailwind CSS + JavaScript
**Target Stack**: Streamlit (pure Python)

---

## Architecture Comparison

### Current Architecture (Flask)

```
┌─────────────────────────────────────────────────────────────┐
│                     Flask Application                         │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                      app.py                               │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │ │
│  │  │ generate_    │  │ calculate_   │  │ generate_    │   │ │
│  │  │ aruco_grid()│  │ transformation│ │ pdf()       │   │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │ │
│  └─────────────────────────────────────────────────────────┘ │
│                        │                                      │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Routes: GET /, POST /api/preview, POST /api/generate │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┴─────────────────────────────────┐
│                      Frontend                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │ │
│  │ templates/  │  │  static/    │  │  static/js/main.js  │   │ │
│  │  index.html │  │  css/style  │  │  (API calls)        │   │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘   │ │
└─────────────────────────────────────────────────────────────┘
```

### Target Architecture (Streamlit)

```
┌─────────────────────────────────────────────────────────────┐
│                     Streamlit Application                     │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                      app.py                               │ │
│  │  ┌─────────────────────────────────────────────────────┐ │ │
│  │  │  Sidebar: User Inputs                               │ │ │
│  │  │  - Paper Settings (A4/A3, Orientation, Dictionary) │ │ │
│  │  │  - Grid Dimensions (Rows, Cols, Size, Separation)  │ │ │
│  │  │  - Display Options (IDs, Scale, Params, Coordsys)  │ │ │
│  │  │  - Coordinate System (Translation/Rotation)         │ │ │
│  │  └─────────────────────────────────────────────────────┘ │ │
│  │                      │                                    │ │
│  │  ┌─────────────────────────────────────────────────────┐ │ │
│  │  │  Main Area: Preview & Export                         │ │ │
│  │  │  - st.image (live preview)                           │ │ │
│  │  │  - Transformation Info (T, quaternion)               │ │ │
│  │  │  - st.download_button (PDF export)                   │ │ │
│  │  └─────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
│                        │                                      │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Reused Core Functions (unchanged):                     │ │
│  │  - generate_aruco_grid()                                 │ │
│  │  - calculate_transformation()                            │ │
│  │  - generate_pdf()                                        │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Detailed Migration Steps

### Step 1: Set Up Streamlit App Structure

**File**: `app.py`

```python
import streamlit as st
import io
import math
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A3, A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from scipy.spatial.transform import Rotation as R_scipy

# Import existing functions (to be copied from current app.py)
from existing_functions import (
    generate_aruco_grid,
    calculate_transformation,
    generate_pdf
)

# Page configuration
st.set_page_config(
    page_title="ArUco Grid Generator",
    page_icon="📷",
    layout="wide"
)

# Title and logo
st.title("ArUco Grid Generator")
```

### Step 2: Create Sidebar with Configuration Parameters

**Location**: `app.py` sidebar section

```python
with st.sidebar:
    st.header("Configuration")
    
    # Paper Settings Section
    st.subheader("Page and Layout")
    paper_size = st.selectbox("Paper Size", ["A4", "A3"])
    orientation = st.selectbox("Orientation", ["portrait", "landscape"])
    dictionary = st.selectbox(
        "ArUco Dictionary",
        ["DICT_4X4_250", "DICT_5X5_250", "DICT_6X6_250", "DICT_7X7_250", "DICT_ARUCO_ORIGINAL"]
    )
    
    # Grid Dimensions Section
    st.subheader("Grid Dimensions")
    cols = st.number_input("Columns", min_value=1, value=5)
    rows = st.number_input("Rows", min_value=1, value=7)
    marker_size_mm = st.number_input("Size (mm)", min_value=1, value=30)
    separation_mm = st.number_input("Separation (mm)", min_value=1, value=10)
    
    # Display Options Section
    st.subheader("Optional Information")
    show_ids = st.checkbox("Marker IDs", value=True)
    show_scale = st.checkbox("Scale", value=True)
    show_params = st.checkbox("Parameters", value=True)
    show_coordsys = st.checkbox("Coordinate System", value=False)
    
    # Coordinate System Section (conditionally visible)
    if show_coordsys:
        st.subheader("Coordinate System")
        base_translation_x = st.number_input("Translation X (mm)", value=0.0, step=0.1)
        base_translation_y = st.number_input("Translation Y (mm)", value=0.0, step=0.1)
        base_translation_z = st.number_input("Translation Z (mm)", value=0.0, step=0.1)
        base_rotation_roll = st.number_input("Roll (deg)", value=0.0, step=0.1)
        base_rotation_pitch = st.number_input("Pitch (deg)", value=0.0, step=0.1)
        base_rotation_yaw = st.number_input("Yaw (deg)", value=0.0, step=0.1)
```

### Step 3: Build Data Dictionary from Inputs

```python
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
    "base_translation": [base_translation_x, base_translation_y, base_translation_z],
    "base_rotation": [base_rotation_roll, base_rotation_pitch, base_rotation_yaw]
}
```

### Step 4: Display Live Preview

```python
# Main area
st.header("Preview")

# Generate low-res preview
preview_img = generate_aruco_grid(data, low_res=True)
st.image(preview_img, caption="Live Preview", use_container_width=True)
```

### Step 5: Add Transformation Information

```python
if show_coordsys:
    st.header("Transformation Information")
    T, t_m, quat = calculate_transformation(data)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Homogeneous Matrix (T)")
        st.write(T)
    
    with col2:
        st.subheader("Translation (m)")
        st.write(f"X: {t_m[0]:.4f}")
        st.write(f"Y: {t_m[1]:.4f}")
        st.write(f"Z: {t_m[2]:.4f}")
    
    with col3:
        st.subheader("Quaternion [x, y, z, w]")
        st.write(f"x: {quat[0]:.4f}")
        st.write(f"y: {quat[1]:.4f}")
        st.write(f"z: {quat[2]:.4f}")
        st.write(f"w: {quat[3]:.4f}")
```

### Step 6: Add PDF Download

```python
st.header("Export")

# Generate PDF
pdf_buffer = generate_pdf(data)

st.download_button(
    label="Download PDF",
    data=pdf_buffer,
    file_name="aruco_grid.pdf",
    mime="application/pdf"
)
```

---

## File Changes Summary

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `app.py` | **Replace** | New Streamlit-based application |
| `requirements.txt` | **Modify** | Add `streamlit` dependency |
| `templates/` | **Delete** | No longer needed |
| `static/` | **Delete** | No longer needed (css, js, images) |

### Updated `requirements.txt`

```
streamlit>=1.28.0
opencv-python-headless>=4.8.0
numpy>=1.24.0
Pillow>=10.0.0
reportlab>=4.0.0
scipy>=1.11.0
```

---

## Running the New Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run Streamlit app
stream

lit run app.py# Or with custom port
streamlit run app.py --server.port 8501
```

Docker update (update `Dockerfile` and `docker-compose.yml`):

```dockerfile
# In Dockerfile, replace:
# CMD ["python", "app.py"]
# With:
CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0"]
```

---

## Benefits of Migration

| Aspect | Before (Flask) | After (Streamlit) |
|--------|----------------|-------------------|
| Lines of code | ~500+ (Python + HTML + JS) | ~150 (Pure Python) |
| Development speed | Moderate (multiple files) | Fast (single file) |
| UI consistency | Manual (Tailwind) | Automatic (Streamlit) |
| State management | Manual (JS + Flask) | Automatic (Session state) |
| Layout flexibility | High (custom HTML) | Moderate (Streamlit API) |
| Dependencies | Flask + Jinja2 | Streamlit |

---

## Known Limitations & Workarounds

| Limitation | Workaround |
|------------|------------|
| No custom favicon | Streamlit uses default, or configure in `st.set_page_config` |
| Limited logo placement | Place in sidebar using `st.image` |
| No collapsible sections (before 1.35) | Use `st.expander` (available in newer versions) |
| Less control over exact pixel positioning | Accept Streamlit's layout system |

---

## Rollback Plan (If Needed)

Keep the original `app.py` as `app_flask.py` in case of issues:

```bash
# To rollback to Flask
mv app.py app_streamlit.py
mv app_flask.py app.py
python app.py
```
