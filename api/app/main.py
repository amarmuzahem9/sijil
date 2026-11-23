"""FastAPI application. Client IP from X-Forwarded-For is trusted only from TRUSTED_PROXY_CIDRS,
which uvicorn enforces via --forwarded-allow-ips (see entrypoint.sh)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import (
    admin,
    admins,
    archive,
    audit,
    auth,
    catalog,
    client_config,
    drafts,
    health,
    marketer,
    marketers,
    settings,
)
from app.config import get_settings
from app.errors import install_error_handlers
from app.logging_config import setup_logging
from app.services import match_service  # noqa: F401  (registers the check source and catalog usage checks)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Card readings left running by a previous process become failed/timeout (specs/006 R5).
    if get_settings().app_env != "test":
        from app.services.card_reading_service import sweep_at_startup

        sweep_at_startup()
    yield


def create_app() -> FastAPI:
    setup_logging()
    config = get_settings()  # fails fast on unsafe staging/production config
    dev = config.app_env in ("development", "test")
    app = FastAPI(
        lifespan=lifespan,
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
        drafts,
        client_config,
    ):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
