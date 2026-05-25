import pytest


@pytest.mark.smoke
def test_import_container():
    from src.app.container import AppContainer

    assert AppContainer is not None