import logging
from pathlib import Path

import pytest
from src.app.container import AppContainer
from src.app.settings import Settings
from src.shared.enums import PipelineExecutorKind, RuntimeMode


@pytest.mark.unit
def test_container_creation():
    settings = Settings(
        project_root=Path("."),
        app={},
        paths={},
        data={},
        logging={},
        runtime={"mode": RuntimeMode.PANDAS},
        dask={},
        pipeline={"executor": PipelineExecutorKind.CLI},
        model={},
        preprocessing={},
        training={},
        evaluation={},
        api={},
        bot={},
    )

    container = AppContainer(
        settings=settings,
        logger=logging.getLogger("test"),
        dask_client=None,
        pipeline_registry={},
    )

    assert container.settings == settings
