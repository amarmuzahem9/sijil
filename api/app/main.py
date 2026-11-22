"""FastAPI application. Client IP from X-Forwarded-For is trusted only from TRUSTED_PROXY_CIDRS,
which uvicorn enforces via --forwarded-allow-ips (see entrypoint.sh)."""

from fastapi import FastAPI

from app.api import (
    admin,
    admins,
    archive,
    audit,
    auth,
    catalog,
    health,
    marketer,
    marketers,
    settings,
)
from app.config import get_settings
from app.errors import install_error_handlers
from app.logging_config import setup_logging


def create_app() -> FastAPI:
    setup_logging()
    config = get_settings()  # fails fast on unsafe staging/production config
    dev = config.app_env in ("development", "test")
    app = FastAPI(
        title="Sijil API",
        docs_url="/api/docs" if dev else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if dev else None,
    )
    install_error_handlers(app)
    for module in (
        health,
        auth,
        marketer,
        admin,
        admins,
        marketers,
        audit,
        archive,
        settings,
        catalog,
    ):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
