"""Application entrypoint for ow-mcp."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
import uvicorn

from app.api.routes import api_router
from app.config import settings
from app.database import Base, engine
from app.mcp_server import mcp
from app import models as _models  # noqa: F401


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    mcp_http_app = mcp.http_app(path="/", transport="streamable-http")

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        Base.metadata.create_all(bind=engine)
        async with mcp_http_app.router.lifespan_context(mcp_http_app):
            yield

    app = FastAPI(title="ow-mcp", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_key.get_secret_value(),
        session_cookie=settings.session_cookie_name,
        max_age=settings.session_max_age_seconds,
        same_site="lax",
        https_only=settings.app_env != "development",
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            content = exc.detail
        else:
            content = {"error": "unexpected_error", "message": str(exc.detail)}
        return JSONResponse(status_code=exc.status_code, content=content)

    app.include_router(api_router)
    app.mount("/mcp", mcp_http_app)
    return app


app = create_app()


def main() -> None:
    """Run the development server."""
    uvicorn.run("app.main:app", host="0.0.0.0", port=8010, reload=False)
