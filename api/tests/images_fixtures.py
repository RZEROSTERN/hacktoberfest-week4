"""Generated test images. The real screenshots are never used in tests: they hold personal
data and are not in version control."""

from pathlib import Path

from PIL import Image, ImageDraw


def solid(path: Path, size: tuple[int, int] = (400, 300), colour: str = "white") -> Path:
    Image.new("RGB", size, colour).save(path)
    return path


def panelled(path: Path, seed: int, size: tuple[int, int] = (400, 300)) -> Path:
    """A deterministic image with enough structure for a perceptual hash to be meaningful.

    A flat colour gives a degenerate dHash (every neighbour equal), so this draws bars whose
    widths depend on `seed`.
    """
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    for index in range(8):
        left = index * size[0] // 8
        shade = (index * 31 + seed * 67) % 256
        draw.rectangle([left, 0, left + size[0] // 8, size[1]], fill=(shade, shade, shade))
    image.save(path)
    return path
