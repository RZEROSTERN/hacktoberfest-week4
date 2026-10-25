import threading
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.catalog import load_catalog
from app.compat import CompatChecker, OllamaCompatChecker
from app.config import Settings
from app.db import make_engine
from app.errors import ApiError
from app.indexing import Indexer
from app.ollama import ModelEngine, OllamaAdmin
from app.organize import Organizer
from app.routes import router
from app.routes_engine import router as engine_router
from app.routes_folders import router as folders_router
from app.routes_runs import router as runs_router
from app.routes_search import router as search_router
from app.routes_settings import router as settings_router
from app.routes_setup import router as setup_router
from app.routes_undo import router as undo_router
from app.runs import RunManager
from app.settings_store import VISION_MODEL, seed_setting, vision_model_getter
from app.setup import SetupManager
from app.vision import OllamaVision, Vision


def create_app(
    settings: Settings | None = None,
    vision: Vision | None = None,
    ollama: ModelEngine | None = None,
    compat: CompatChecker | None = None,
) -> FastAPI:
    """The engines can be swapped in tests; the defaults are the real ones."""
    settings = settings or Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.models_dir.mkdir(parents=True, exist_ok=True)

    engine = make_engine(settings.data_dir)
    seed_setting(engine, VISION_MODEL, settings.vision_model)

    # One worker for everything heavy. The resource budget allows one image in flight at a time,
    # so scanning, analysis and organizing never overlap.
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="job")

    engine_vision: Vision = vision or OllamaVision(
        settings.ollama_url, vision_model_getter(engine), prompts_dir=settings.prompts_dir
    )
    # Shared between the indexer, which reads it between images, and the manager, which sets
    # it when the desktop says the machine is back in use, on battery, or past the window.
    pause = threading.Event()
    indexer = Indexer(engine, engine_vision, settings.max_image_px, should_pause=pause.is_set)
    runs = RunManager(engine, indexer, Organizer(engine), executor, engine_vision, pause)
    runs.recover()

    # Downloads are mostly waiting for the network, so they get their own worker and never
    # block a sorting run.
    setup_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="setup")
    model_engine = ollama or OllamaAdmin(settings.ollama_url)
    setup = SetupManager(
        engine,
        load_catalog(),
        model_engine,
        compat or OllamaCompatChecker(settings.ollama_url, prompts_dir=settings.prompts_dir),
        setup_executor,
        settings.models_dir,
    )
    setup.recover()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        setup.stop()
        executor.shutdown(wait=True, cancel_futures=True)
        setup_executor.shutdown(wait=True, cancel_futures=True)

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
    app.state.runs = runs
    app.state.setup = setup
    app.state.ollama = model_engine
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.include_router(folders_router)
    app.include_router(engine_router)
    app.include_router(runs_router)
    app.include_router(undo_router)
    app.include_router(search_router)
    app.include_router(settings_router)
    app.include_router(setup_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
