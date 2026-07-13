# ArUcoGridGen v2

A MATCH-branded web workspace for generating detector-valid ArUco grids, ChArUco boards, and checkerboards for robotics and computer-vision calibration.

The v2 application uses a React/TypeScript frontend and a typed FastAPI backend. One immutable millimetre-based scene drives the capped PNG preview, one-page vector PDF, deterministic JSON manifest, automatic page fitting, and exact 100 mm ruler geometry.

## Run locally

Requires Python 3.12, [uv](https://docs.astral.sh/uv/), and Node 22.

```bash
uv sync --all-groups
cd frontend && npm ci && npm run build && cd ..
uv run uvicorn main:app --host 0.0.0.0 --port 8501
```

Open <http://localhost:8501>. For frontend development, run `npm run dev` in `frontend`; Vite proxies `/api` to the backend on port 8501.

## Verification

```bash
uv run pytest --cov=backend
uv run ruff check backend main.py
cd frontend && npm run lint && npm run typecheck && npm run test:coverage && npm run build
cd frontend && npx playwright test
```

Regenerate the checked-in OpenAPI contract after backend schema changes:

```bash
uv run python scripts/export_openapi.py
cd frontend && npm run generate:api
```

## Docker

For fast local testing, build the current checkout with the development Compose file. Docker reuses the dependency and frontend build layers between runs:

```bash
docker compose -f docker-compose.dev.yml up --build
```

Use `ARUCOGRIDGEN_PORT` if port `8501` is already occupied:

```bash
ARUCOGRIDGEN_PORT=8502 docker compose -f docker-compose.dev.yml up --build
```

The regular Compose file continues to run the published image:

```bash
docker compose up
```

The combined non-root container serves both the SPA and API on port `8501`. Readiness is available at `/api/v2/health`.

## API v2

- `GET /api/v2/capabilities`
- `POST /api/v2/fit`
- `POST /api/v2/preview`
- `POST /api/v2/exports/pdf`
- `POST /api/v2/exports/config`
- `GET /api/v2/health`

Requests are strict and versioned. Legacy Streamlit payloads and pixel-identical v1 output are intentionally unsupported.
