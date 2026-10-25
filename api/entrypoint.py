"""PyInstaller entry point.

Kept separate from `app/__main__.py` so the frozen binary has a single, import-safe module to
start from, and so multiprocessing on Windows does not re-run the server on spawn.
"""

import multiprocessing

import uvicorn

from app.config import Settings
from app.main import create_app


def main() -> None:
    settings = Settings()
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level="warning",
        access_log=False,  # request paths can contain file names; they are never logged
    )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
