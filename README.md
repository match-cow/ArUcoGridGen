# ArUco Grid Generator

Web app for generating printable ArUco marker grids for computer vision and robotics.

## Quick Start

```bash
git clone https://github.com/yourusername/arucogridgen.git
cd arucogridgen
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## Docker

### Using Docker Compose (pulls pre-built image)

```bash
docker compose up
```

### Using Docker (pre-built image)

```bash
docker run -p 8501:8501 ghcr.io/match-cow/arucogridgen:main
```

### Using Docker (build locally)

```bash
docker build -t arucogridgen . && docker run -p 8501:8501 arucogridgen
```

Access at http://localhost:8501
