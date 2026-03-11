"""Route registry."""

from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.connection import router as connection_router
from app.api.routes.ui import router as ui_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(connection_router)
api_router.include_router(ui_router)
