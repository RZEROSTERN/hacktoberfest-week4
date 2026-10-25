"""Reading, hashing and downscaling screenshots. No model is involved here.

Duplicate detection is deliberately cheap and runs before any inference:

- Exact duplicates come from the SHA-256 of the file's bytes.
- Near duplicates come from a 64-bit difference hash (dHash). dHash is implemented here with
  Pillow alone rather than pulling in `imagehash`, which would drag numpy and scipy into the
  PyInstaller bundle for one function. See docs/DECISIONS.md.

Nothing in this module logs image contents.
"""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.errors import ApiError

# Formats Pillow reads that a screenshot realistically arrives in. Anything else is skipped
# rather than guessed at.
SUPPORTED_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".tif"})

# dHash compares each pixel with its right-hand neighbour on a 9x8 grid, giving 8x8 = 64 bits.
_DHASH_W = 9
_DHASH_H = 8

CHUNK = 1024 * 1024


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_SUFFIXES


def content_hash(path: Path) -> str:
    """SHA-256 of the file's bytes, read in chunks so a large image never lands in memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def dhash(image: Image.Image) -> str:
    """64-bit difference hash as 16 hex characters."""
    small = image.convert("L").resize((_DHASH_W, _DHASH_H), Image.Resampling.LANCZOS)
    # tobytes() on a greyscale image is row-major, one byte per pixel, and unlike getdata()
    # it is not deprecated.
    pixels = small.tobytes()
    bits = 0
    for row in range(_DHASH_H):
        offset = row * _DHASH_W
        for col in range(_DHASH_H):
            bits <<= 1
            if pixels[offset + col] > pixels[offset + col + 1]:
                bits |= 1
    return f"{bits:016x}"


def hamming(left: str, right: str) -> int:
    """Number of differing bits between two dHashes. 0 means visually identical."""
    return bin(int(left, 16) ^ int(right, 16)).count("1")


@dataclass(frozen=True)
class LoadedImage:
    image: Image.Image  # downscaled, RGB, ready for the model
    width: int  # original dimensions, before downscaling
    height: int
    perceptual_hash: str


def load_for_analysis(path: Path, max_px: int) -> LoadedImage:
    """Open an image, take its dHash at full size, and downscale it for inference.

    The dHash is taken before downscaling so it does not change when `max_px` is retuned.
    """
    try:
        with Image.open(path) as opened:
            opened.load()
            width, height = opened.size
            phash = dhash(opened)
            image = opened.convert("RGB")
    except UnidentifiedImageError as exc:
        raise ApiError(400, "unsupported_file_type") from exc
    except (OSError, ValueError) as exc:
        raise ApiError(400, "image_unreadable") from exc

    longest = max(width, height)
    if longest > max_px:
        scale = max_px / longest
        image = image.resize(
            (max(1, round(width * scale)), max(1, round(height * scale))), Image.Resampling.LANCZOS
        )
    return LoadedImage(image=image, width=width, height=height, perceptual_hash=phash)


def captured_at(path: Path) -> datetime:
    """When the screenshot was taken, as far as the filesystem knows.

    The modification time is used, not the creation time: it is the only one of the two that
    every platform reports the same way through pathlib.
    """
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
