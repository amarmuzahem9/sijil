"""FastAPI application. Client IP from X-Forwarded-For is trusted only from TRUSTED_PROXY_CIDRS,
which uvicorn enforces via --forwarded-allow-ips (see entrypoint.sh)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import (
    admin,
    admin_backup,
    admin_commissions,
    admin_imports,
    admin_links,
    admin_requests,
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
    notifications,
    requests,
    settings,
)
from app.config import get_settings
from app.errors import install_error_handlers
from app.logging_config import setup_logging
from app.services import (
    legacy_source,  # noqa: F401  (registers legacy subscribers, specs/014)
    match_service,  # noqa: F401  (registers the check source and catalog usage checks)
    sas_source,  # noqa: F401  (registers SAS subscribers, specs/015)
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Card readings left running by a previous process become failed/timeout (specs/006 R5).
    if get_settings().app_env != "test":
        from app.services import legacy_import_service, sas_import_service
        from app.services.card_reading_service import sweep_at_startup

        sweep_at_startup()
        # Legacy previews left fetching by a previous process become failed (specs/014 R8).
        legacy_import_service.sweep_at_startup()
        # SAS previews past their hour are removed (specs/015 R12).
        sas_import_service.sweep_at_startup()
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
        admin_backup,
        admin_imports,
        admin_requests,
        admin_links,
        admin_commissions,
        admins,
        marketers,
        audit,
        archive,
        settings,
        catalog,
        drafts,
        requests,
        notifications,
        client_config,
    ):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
