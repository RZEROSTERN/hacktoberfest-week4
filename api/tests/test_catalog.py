import pytest

from app.catalog import ModelNameError, load_catalog, validate_model_name


class TestCatalog:
    def test_loads_and_has_exactly_one_default(self) -> None:
        catalog = load_catalog()
        assert [m.recommended for m in catalog.vision].count(True) == 1
        assert catalog.recommended.model == "qwen3-vl:2b-instruct"

    def test_every_entry_carries_what_the_wizard_must_show(self) -> None:
        """The wizard promises size, RAM needed and license before any download starts."""
        for model in load_catalog().vision:
            assert model.size_bytes > 0
            assert model.ram_gb > 0
            assert model.license
            assert model.note

    def test_the_model_that_missed_a_sensitive_screenshot_is_not_offered(self) -> None:
        # gemma4:e2b failed the safety gate in the spike, so it is not a choice at any size.
        assert load_catalog().find("gemma4:e2b") is None

    def test_the_default_fits_the_resource_budget(self) -> None:
        """The default must be runnable on an 8 GB machine; the heavier option is opt-in."""
        catalog = load_catalog()
        assert catalog.recommended.ram_gb <= 8
        assert catalog.find("gemma4:e4b") is not None

    def test_measured_downscale_size_matches_the_shipped_default(self) -> None:
        from app.config import Settings

        default_px = Settings.model_fields["max_image_px"].default
        assert all(m.max_image_px == default_px for m in load_catalog().vision)


class TestModelNames:
    @pytest.mark.parametrize(
        "name", ["gemma4:e4b", "qwen3-vl:2b-instruct", "user/model:q4", "moondream"]
    )
    def test_accepts_library_style_names(self, name: str) -> None:
        assert validate_model_name(f"  {name} ") == name

    @pytest.mark.parametrize("name", ["", "   ", "has space", "-leading", "x" * 201, "../escape"])
    def test_refuses_malformed_names(self, name: str) -> None:
        with pytest.raises(ModelNameError) as caught:
            validate_model_name(name)
        assert caught.value.code == "invalid_model_name"

    @pytest.mark.parametrize("name", ["gemma4:cloud", "qwen3-vl:235b-cloud", "cloud/model"])
    def test_refuses_cloud_models_because_they_run_on_someone_elses_computer(
        self, name: str
    ) -> None:
        with pytest.raises(ModelNameError) as caught:
            validate_model_name(name)
        assert caught.value.code == "cloud_model"
