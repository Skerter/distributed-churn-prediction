import logging

from src.app.container import AppContainer
from src.app.settings import Settings


def test_container_creation():
    container = AppContainer(
        settings=Settings(),
        logger=logging.getLogger(__name__),
        dask_client=None,
        pipeline_registry={},
    )

    assert container is not None