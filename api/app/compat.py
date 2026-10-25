"""The compatibility check: can this model actually read an image on this computer?

The recommended list only holds vision models, but the wizard also lets the user name any model
in the Ollama library, and a text-only model asked for a description will happily invent one.
So the check does not ask the model whether it can see. It renders a short token into a test
image and requires the token back.

A model that cannot read images has no way to produce it. One that can, but is too weak to read
plain high-contrast text, would also be useless for screenshots, so failing here is the right
answer either way.

The image is generated rather than shipped, so there is one less file to bundle and no asset
that can go missing from the packaged binary.
"""

import threading
from pathlib import Path
from typing import Protocol

import httpx
from PIL import Image, ImageDraw, ImageFont

from app.errors import ApiError
from app.vision import OllamaVision

# Deliberately unguessable from the prompt alone, and short enough that reading it is not a
# test of OCR quality. Letters and digits, no ambiguous pairs.
CHECK_TOKEN = "7314"
CHECK_WORD = "SLOTHSHOT"


class CompatError(Exception):
    """The model failed the check; `code` is a stable error code for the UI."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class CompatChecker(Protocol):
    def check(self, model: str, cancel: threading.Event) -> None:
        """Return normally when the model passes; raise CompatError otherwise."""
        ...


def test_image() -> Image.Image:
    """A plain, high-contrast card carrying the token. Nothing subtle to read."""
    image = Image.new("RGB", (640, 360), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        for path in (
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf",
        ):
            if Path(path).exists():
                try:
                    return ImageFont.truetype(path, size)
                except OSError:
                    continue
        return ImageFont.load_default(size=size)

    draw.rectangle([0, 0, 639, 359], outline=(20, 20, 20), width=6)
    draw.text((320, 130), CHECK_WORD, font=font(54), fill=(20, 20, 20), anchor="mm")
    draw.text((320, 225), CHECK_TOKEN, font=font(84), fill=(20, 20, 20), anchor="mm")
    return image


_CODES = {
    "vision_model_missing": "compat_model_missing",
    "vision_unreachable": "ollama_unreachable",
    "vision_timeout": "compat_timeout",
    "invalid_model_output": "compat_invalid_output",
}


def _read_the_token(text: str, description: str, slug: str) -> bool:
    """Did the answer come back carrying what was written in the picture?"""
    haystack = f"{text} {description} {slug}".upper()
    return CHECK_TOKEN in haystack or CHECK_WORD in haystack


class OllamaCompatChecker:
    def __init__(
        self,
        ollama_url: str,
        prompts_dir: Path | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 120.0,
    ) -> None:
        self._url = ollama_url
        self._prompts_dir = prompts_dir
        self._transport = transport
        self._timeout = timeout

    def check(self, model: str, cancel: threading.Event) -> None:
        vision = OllamaVision(
            self._url,
            lambda: model,
            prompts_dir=self._prompts_dir,
            timeout=self._timeout,
            transport=self._transport,
        )
        try:
            result = vision.analyze(test_image())
        except ApiError as exc:
            raise CompatError(_CODES.get(exc.code, "compat_no_vision")) from exc

        analysis = result.analysis
        if not _read_the_token(analysis.text, analysis.description, analysis.slug):
            # It answered in the right shape without reading the picture, which is exactly what
            # a text-only model does.
            raise CompatError("compat_no_vision")
