from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from SLOTHSHOT_* environment variables.

    Nothing is defaulted except the loopback bind address: the desktop shell (or
    `make dev`) decides ports, directories and the Ollama URL.
    """

    model_config = SettingsConfigDict(env_prefix="SLOTHSHOT_")

    host: str = "127.0.0.1"
    port: int = Field(ge=1, le=65535)
    data_dir: Path
    models_dir: Path
    ollama_url: str
    cors_origins: list[str] = []

    # Vision model. The tag is NOT hard-coded anywhere: the model in use is read from the local
    # settings table. This variable only seeds that table on start when nothing is stored yet
    # (development); the setup wizard writes it in the packaged app.
    vision_model: str | None = None

    # Longest side, in pixels, that an image is downscaled to before inference.
    # 768, from the spike: both candidate models scored identically at 768 and 1024, and 768
    # costs noticeably less memory, which is the budget that actually binds.
    # See docs/BENCHMARKS.md.
    max_image_px: int = Field(default=768, ge=256, le=4096)

    # Folder with the versioned prompt files; defaults to the `prompts` folder next to the app
    # package (which is also where the packaged binary unpacks it).
    prompts_dir: Path | None = None

    # Process id of the desktop app that started this api. When it disappears the api shuts down.
    parent_pid: int | None = None
