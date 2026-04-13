from app.core.config import get_settings


def test_settings_paths_are_resolved():
    settings = get_settings()
    assert settings.static_path.name == "static"
    assert settings.templates_path.name == "templates"


def test_settings_are_cached():
    first = get_settings()
    second = get_settings()
    assert first is second
