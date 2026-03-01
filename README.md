# ArUco Grid Generator

Web app for generating printable ArUco marker grids for computer vision and robotics.

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
