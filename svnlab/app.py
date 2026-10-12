from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import router
from .cache import SourceCache
from .config import DEFAULT_SETTINGS, Settings
from .errors import SvnLabError
from .svn_client import SvnClient

STATIC_DIR = Path(__file__).with_name("static")


def create_app(
    *,
    settings: Settings = DEFAULT_SETTINGS,
    svn_client: SvnClient | None = None,
    source_cache: SourceCache | None = None,
) -> FastAPI:
    app = FastAPI(
        title="SVNLab",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.svn_client = svn_client or SvnClient(settings)
    app.state.source_cache = source_cache or SourceCache(
        ttl_seconds=settings.cache_ttl_seconds,
        max_entries=settings.cache_max_entries,
        max_bytes=settings.cache_max_bytes,
    )

    @app.exception_handler(SvnLabError)
    async def handle_svn_error(_: Request, exc: SvnLabError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "message": exc.message, "hint": exc.hint},
        )

    @app.middleware("http")
    async def api_privacy_headers(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    app.include_router(router)
    app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()

