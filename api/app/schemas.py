"""What the model is asked to return, and what the api will accept back.

The same schema is handed to Ollama as `format`, so the model is constrained rather than asked
politely, and used to validate the answer afterwards. A model can still return something that
fits the shape but not the rules (an empty slug, an unknown category), which is why the
validators below exist.
"""

import re

from pydantic import BaseModel, Field, field_validator

from app.models import Category

SLUG_RE = re.compile(r"[^a-z0-9]+")
MAX_SLUG_WORDS = 6
MAX_TEXT_CHARS = 2000


class Analysis(BaseModel):
    """One screenshot, as the vision model describes it."""

    slug: str = Field(min_length=1)
    category: Category
    description: str = ""
    text: str = ""
    sensitive: bool = False
    expiry_hint: str | None = None

    @field_validator("slug")
    @classmethod
    def clean_slug(cls, value: str) -> str:
        """Models drift: they add extensions, capitals, accents and stray words.

        The slug becomes part of a filename on three operating systems, so it is normalised
        here rather than trusted.
        """
        lowered = value.strip().lower()
        lowered = re.sub(r"\.(png|jpe?g|webp|gif|bmp|tiff?)$", "", lowered)
        words = [w for w in SLUG_RE.sub("-", lowered).split("-") if w]
        if not words:
            raise ValueError("slug is empty after cleaning")
        return "-".join(words[:MAX_SLUG_WORDS])

    @field_validator("text")
    @classmethod
    def cap_text(cls, value: str) -> str:
        # A model that decides to transcribe an entire document would otherwise bloat the index.
        return value.strip()[:MAX_TEXT_CHARS]

    @field_validator("expiry_hint")
    @classmethod
    def blank_is_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None
