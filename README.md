<p align="center">
  <img src="static/match.png" alt="MATCH" width="260">
</p>

# PoseGridGen

Generate detector-ready ArUco grids, ChArUco boards, and checkerboards for robotics and computer-vision calibration.

PoseGridGen provides a live browser preview and exports print-ready vector PDFs plus deterministic JSON configuration files. Board geometry is defined in millimetres and includes automatic page fitting, print compensation, an optional 100 mm ruler, and coordinate-frame metadata.

## Run locally

Requires Python 3.12, [uv](https://docs.astral.sh/uv/), and Node.js 22.

```bash
uv sync --all-groups
cd frontend
npm ci
npm run build
cd ..
uv run uvicorn main:app --host 0.0.0.0 --port 8501
```

Open <http://localhost:8501>.

For frontend development, run `npm run dev` in `frontend`; Vite proxies API requests to the backend on port `8501`.

## Docker

Run the published image:

```bash
docker compose up
```

Build and run the current checkout:

```bash
docker compose -f docker-compose.dev.yml up --build
```

Set `POSEGRIDGEN_PORT` to use another host port:

```bash
POSEGRIDGEN_PORT=8502 docker compose -f docker-compose.dev.yml up --build
```

## Development

```bash
uv run pytest --cov=backend
uv run ruff check backend main.py scripts
cd frontend
npm run lint
npm run typecheck
npm run test:coverage
npm run build
npx playwright test
```

After changing the backend schema, regenerate the checked-in API contract:

```bash
uv run python scripts/export_openapi.py
cd frontend && npm run generate:api
```
