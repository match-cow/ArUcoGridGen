from __future__ import annotations

import hashlib
import json
import logging
import uuid
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .constants import CHARUCO_DICTIONARIES, DICTIONARIES, EDGE_CLEARANCE_MM, PAPER_SIZES_MM
from .errors import FitError
from .fit import fit_request
from .models import FitResponse, GenerateRequest
from .render import manifest, render_pdf, render_png
from .scene import Scene, build_scene

log = logging.getLogger("posegridgen")
app = FastAPI(title="PoseGridGen", version="2.0.0")
_cache: OrderedDict[str, Scene] = OrderedDict()
_CACHE_LIMIT = 64


def canonical(req: GenerateRequest) -> tuple[str, bytes]:
    raw = json.dumps(
        req.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(raw).hexdigest(), raw


def scene_for(req: GenerateRequest) -> tuple[str, Scene]:
    config_hash, _ = canonical(req)
    if config_hash in _cache:
        scene = _cache.pop(config_hash)
        _cache[config_hash] = scene
        return config_hash, scene
    scene = build_scene(req)
    _cache[config_hash] = scene
    while len(_cache) > _CACHE_LIMIT:
        _cache.popitem(last=False)
    return config_hash, scene


@app.exception_handler(FitError)
async def fit_error(_: Request, exc: FitError):
    return JSONResponse(status_code=422, content={"errors": [exc.detail()]})


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    errors = []
    for item in exc.errors():
        path = [part for part in item["loc"] if part != "body"]
        errors.append({"code": item["type"], "path": path, "message": item["msg"]})
    return JSONResponse(status_code=422, content={"errors": errors})


@app.exception_handler(Exception)
async def unexpected(_: Request, exc: Exception):
    request_id = str(uuid.uuid4())
    log.exception("Unhandled request %s", request_id, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"request_id": request_id, "message": "An unexpected error occurred"},
    )


@app.get("/api/v2/health")
async def health():
    return {"status": "ok"}


@app.get("/api/v2/capabilities")
async def capabilities():
    return {
        "schema_version": "2.0",
        "paper_sizes_mm": PAPER_SIZES_MM,
        "dictionaries": DICTIONARIES,
        "charuco_dictionaries": CHARUCO_DICTIONARIES,
        "limits": {
            "grid": 100,
            "physical_mm": 200,
            "checkerboard_border_mm": 100,
            "preview_max_pixels": 1600,
            "page_edge_clearance_mm": EDGE_CLEARANCE_MM,
        },
        "board_types": ["aruco", "charuco", "checkerboard"],
        "defaults": GenerateRequest().model_dump(mode="json"),
        "board_defaults": {
            "aruco": GenerateRequest().board.model_dump(mode="json"),
            "charuco": {
                "type": "charuco",
                "dictionary": "DICT_5X5_250",
                "squares_x": 5,
                "squares_y": 7,
                "square_size_mm": 30,
                "marker_size_mm": 18,
            },
            "checkerboard": {
                "type": "checkerboard",
                "squares_x": 5,
                "squares_y": 8,
                "square_size_mm": 30,
                "border_mm": 20,
            },
        },
    }


@app.post("/api/v2/preview")
async def preview(req: GenerateRequest):
    config_hash, scene = scene_for(req)
    return Response(
        render_png(scene),
        media_type="image/png",
        headers={"X-Configuration-Hash": config_hash, "Cache-Control": "no-store"},
    )


@app.post(
    "/api/v2/fit",
    response_model=FitResponse,
    responses={422: {"description": "No safe reduced configuration exists"}},
)
async def fit(req: GenerateRequest):
    return fit_request(req)


@app.post("/api/v2/exports/pdf")
async def pdf(req: GenerateRequest):
    config_hash, scene = scene_for(req)
    return Response(
        render_pdf(scene),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="calibration-board.pdf"',
            "X-Configuration-Hash": config_hash,
        },
    )


@app.post("/api/v2/exports/config")
async def config(req: GenerateRequest):
    config_hash, scene = scene_for(req)
    return Response(
        manifest(scene, config_hash),
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="calibration-board.json"',
            "X-Configuration-Hash": config_hash,
        },
    )


DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        candidate = DIST / path
        return FileResponse(candidate if candidate.is_file() else DIST / "index.html")
