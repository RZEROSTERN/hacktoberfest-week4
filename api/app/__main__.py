"""`python -m app` in development. The packaged binary uses entrypoint.py instead."""

import uvicorn

from app.config import Settings
from app.main import create_app

if __name__ == "__main__":
    settings = Settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_level="info")
