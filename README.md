# ArUco Grid Generator

Web app for generating printable ArUco marker grids for computer vision and robotics.

## Features

- Custom grid parameters (paper size, ArUco dictionary, rows/columns, marker size, separation)
- Live preview while adjusting settings
- Optional overlays (IDs, scale ruler, parameters, coordinate system)
- Robotics coordinate system with transformation matrices
- High-resolution PDF export

## Quick Start

```bash
git clone https://github.com/yourusername/arucogridgen.git
cd arucogridgen
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## Docker

```bash
docker-compose up --build
```

Access at http://localhost:8501
