import pytest


@pytest.mark.smoke
def test_import_settings():
    from src.app.settings import Settings

    assert Settings is not None