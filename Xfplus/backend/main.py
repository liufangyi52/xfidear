from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import get_settings
from backend.routers import ai, alerts, auth, broadcasts, command, incidents, map_tiles, messages, meta, notifications, risk
from backend.services.seed_service import initialize_database
from backend.services.storage import ensure_seed_files

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(alerts.router)
app.include_router(auth.router)
app.include_router(ai.router)
app.include_router(risk.router)
app.include_router(meta.router)
app.include_router(broadcasts.router)
app.include_router(messages.router)
app.include_router(command.router)
app.include_router(incidents.router)
app.include_router(notifications.router)
app.include_router(map_tiles.router)

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"
NO_STORE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

if FRONTEND_DIST.exists():
    @app.get("/assets/{asset_path:path}", include_in_schema=False)
    def serve_asset(asset_path: str):
        asset_root = FRONTEND_ASSETS.resolve()
        asset_file = (asset_root / asset_path).resolve()

        if asset_root not in asset_file.parents:
            return Response(status_code=404)

        if asset_file.is_file():
            return FileResponse(asset_file, headers={"Cache-Control": "no-cache, max-age=0"})

        if asset_file.suffix == ".js":
            return Response(
                """
const url = new URL(window.location.href);
url.searchParams.set("_asset_refresh", Date.now().toString());
window.location.replace(url.toString());
const fallbackExport = {};
export const A = fallbackExport;
export const B = fallbackExport;
export const C = fallbackExport;
export const D = fallbackExport;
export const E = fallbackExport;
export const F = fallbackExport;
export const G = fallbackExport;
export const H = fallbackExport;
export const I = fallbackExport;
export const J = fallbackExport;
export const K = fallbackExport;
export const L = fallbackExport;
export const M = fallbackExport;
export const N = fallbackExport;
export const O = fallbackExport;
export const P = fallbackExport;
export const Q = fallbackExport;
export const R = fallbackExport;
export const S = fallbackExport;
export const T = fallbackExport;
export const U = fallbackExport;
export const V = fallbackExport;
export const W = fallbackExport;
export const X = fallbackExport;
export const Y = fallbackExport;
export const Z = fallbackExport;
export const a = fallbackExport;
export const b = fallbackExport;
export const c = fallbackExport;
export const d = fallbackExport;
export const e = fallbackExport;
export const f = fallbackExport;
export const g = fallbackExport;
export const h = fallbackExport;
export const i = fallbackExport;
export const j = fallbackExport;
export const k = fallbackExport;
export const l = fallbackExport;
export const m = fallbackExport;
export const n = fallbackExport;
export const o = fallbackExport;
export const p = fallbackExport;
export const q = fallbackExport;
export const r = fallbackExport;
export const s = fallbackExport;
export const t = fallbackExport;
export const u = fallbackExport;
export const v = fallbackExport;
export const w = fallbackExport;
export const x = fallbackExport;
export const y = fallbackExport;
export const z = fallbackExport;
export default fallbackExport;
""".strip(),
                media_type="application/javascript",
                headers=NO_STORE_HEADERS,
            )

        if asset_file.suffix == ".css":
            return Response("", media_type="text/css", headers=NO_STORE_HEADERS)

        return Response(status_code=404)

    for static_name in ["favicon.svg", "icons.svg"]:
        static_path = FRONTEND_DIST / static_name

        if static_path.exists():
            route_path = f"/{static_name}"

            @app.get(route_path, include_in_schema=False)
            def serve_static_file(path: Path = static_path):
                return FileResponse(path, headers={"Cache-Control": "no-cache, max-age=0"})


@app.on_event("startup")
def startup() -> None:
    ensure_seed_files()
    initialize_database()


@app.get("/api/health")
def health():
    return {"ok": True, "name": settings.app_name}


if FRONTEND_DIST.exists():
    INDEX_HTML = FRONTEND_DIST / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        return FileResponse(INDEX_HTML, headers=NO_STORE_HEADERS)
