"""HTTP API of the card reader (specs/006-card-ocr/contracts/ocr-service.md).

- GET /health: 503 until the models are loaded, then 200.
- POST /read: one photo (multipart `image` + `side`); one reading at a time.

No request body, field text or number is ever logged or echoed in an error.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from service import reader

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("ocr.app")

MAX_IMAGE_BYTES = 6 * 1024 * 1024


class _State:
    models: reader.Models | None = None
    load_error: str | None = None


state = _State()
_lock = asyncio.Lock()


def _load_models() -> None:
    try:
        state.models = reader.load()
    except Exception as exc:  # reported by /health; the container healthcheck fails
        state.load_error = type(exc).__name__
        log.error("loading the models failed: %s", type(exc).__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Load in the background so the process answers /health (503) while loading.
    threading.Thread(target=_load_models, name="load-models", daemon=True).start()
    yield


app = FastAPI(title="Sijil card reader", docs_url=None, redoc_url=None, openapi_url=None,
              lifespan=lifespan)


def _error(status: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code})


@app.get("/health")
def health() -> JSONResponse:
    if state.models is None:
        return JSONResponse(
            status_code=503,
            content={"status": "loading" if state.load_error is None else "error",
                     "models": "not_loaded"},
        )
    return JSONResponse(
        content={"status": "ok", "models": "loaded", "upstream": reader.UPSTREAM_COMMIT}
    )


@app.post("/read")
async def read(
    image: Annotated[UploadFile, File()],
    side: Annotated[Literal["front", "back"], Form()],
) -> JSONResponse:
    if state.models is None:
        return _error(503, "loading")
    data = await image.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        return _error(413, "image_too_large")
    decoded = reader.decode(data)
    if decoded is None:
        return _error(400, "bad_image")
    async with _lock:  # one inference at a time: the container has 2 CPUs
        try:
            result = await run_in_threadpool(reader.read, state.models, decoded)
        except Exception as exc:
            log.error("reading failed (%s side): %s", side, type(exc).__name__)
            return _error(500, "reader_error")
    return JSONResponse(content=result)
