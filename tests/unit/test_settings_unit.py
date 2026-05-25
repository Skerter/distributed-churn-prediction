from pathlib import Path

import pytest

from src.app.settings import Settings
from src.shared.enums import RuntimeMode, PipelineExecutorKind


@pytest.mark.unit
def test_settings_creation():
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

    assert settings is not None