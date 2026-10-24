from pathlib import Path

import pytest
from PIL import Image

from app.errors import ApiError
from app.images import (
    captured_at,
    content_hash,
    dhash,
    hamming,
    is_supported,
    load_for_analysis,
)
from tests.images_fixtures import panelled, solid


def test_is_supported_accepts_screenshot_formats_and_rejects_video(tmp_path: Path) -> None:
    assert is_supported(tmp_path / "shot.png")
    assert is_supported(tmp_path / "SHOT.PNG")  # suffix match is case-insensitive
    assert is_supported(tmp_path / "shot.webp")
    assert not is_supported(tmp_path / "recording.mp4")


def test_content_hash_is_stable_and_distinguishes_files(tmp_path: Path) -> None:
    first = panelled(tmp_path / "a.png", seed=1)
    copy = tmp_path / "a-copy.png"
    copy.write_bytes(first.read_bytes())
    other = panelled(tmp_path / "b.png", seed=5)

    assert content_hash(first) == content_hash(copy)
    assert content_hash(first) != content_hash(other)


def test_dhash_matches_an_exact_copy(tmp_path: Path) -> None:
    original = panelled(tmp_path / "a.png", seed=2)
    with Image.open(original) as image:
        first = dhash(image)
    with Image.open(original) as image:
        assert hamming(first, dhash(image)) == 0


def test_dhash_survives_a_resize(tmp_path: Path) -> None:
    """A screenshot resaved at a different size is still the same screenshot."""
    original = panelled(tmp_path / "a.png", seed=3)
    with Image.open(original) as image:
        full = dhash(image)
        smaller = image.resize((image.width // 2, image.height // 2))
    assert hamming(full, dhash(smaller)) <= 6


def test_dhash_separates_different_images(tmp_path: Path) -> None:
    with Image.open(panelled(tmp_path / "a.png", seed=1)) as image:
        first = dhash(image)
    with Image.open(panelled(tmp_path / "b.png", seed=9)) as image:
        second = dhash(image)
    assert hamming(first, second) > 6


def test_load_for_analysis_downscales_to_the_budget(tmp_path: Path) -> None:
    path = panelled(tmp_path / "big.png", seed=4, size=(3456, 2234))
    loaded = load_for_analysis(path, max_px=1024)

    assert (loaded.width, loaded.height) == (3456, 2234)  # original size is preserved
    assert max(loaded.image.size) == 1024  # what the model receives
    assert loaded.image.mode == "RGB"


def test_load_for_analysis_leaves_small_images_alone(tmp_path: Path) -> None:
    path = panelled(tmp_path / "small.png", seed=4, size=(582, 138))
    loaded = load_for_analysis(path, max_px=1024)
    assert loaded.image.size == (582, 138)


def test_perceptual_hash_does_not_change_with_the_downscale_budget(tmp_path: Path) -> None:
    """Retuning max_image_px must not invalidate hashes already stored in the database."""
    path = panelled(tmp_path / "big.png", seed=6, size=(2000, 1500))
    assert (
        load_for_analysis(path, 1024).perceptual_hash
        == load_for_analysis(path, 768).perceptual_hash
    )


def test_unreadable_file_is_refused_not_guessed(tmp_path: Path) -> None:
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"this is not a png")
    with pytest.raises(ApiError) as caught:
        load_for_analysis(broken, max_px=1024)
    assert caught.value.code == "unsupported_file_type"


def test_captured_at_reads_the_modification_time(tmp_path: Path) -> None:
    path = solid(tmp_path / "a.png")
    assert captured_at(path).timestamp() == pytest.approx(path.stat().st_mtime)
