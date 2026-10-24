from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings
from app.db import make_engine
from app.errors import ApiError
from app.routes import router
from app.settings_store import VISION_MODEL, seed_setting


def create_app(settings: Settings | None = None) -> FastAPI:
    """The engines can be swapped in tests; the defaults are the real ones."""
    settings = settings or Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.models_dir.mkdir(parents=True, exist_ok=True)

    engine = make_engine(settings.data_dir)
    seed_setting(engine, VISION_MODEL, settings.vision_model)

    # One worker for everything heavy. The resource budget allows one image in flight at a time,
    # so scanning, analysis and organizing never overlap.
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="job")

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(title="Slothshot API", lifespan=lifespan)

    @app.exception_handler(ApiError)
    async def refuse(_request: Request, exc: ApiError) -> JSONResponse:
        # `detail` is the English text, as FastAPI always sends it; a client can translate by
        # `code` and `params`.
        return JSONResponse(
            {"detail": exc.detail, "code": exc.code, "params": exc.params},
            status_code=exc.status_code,
            headers=exc.headers,
        )

    app.state.settings = settings
    app.state.engine = engine
    app.state.executor = executor
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
