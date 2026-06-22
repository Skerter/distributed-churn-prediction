import pytest


@pytest.mark.integration
def test_pipeline_import():
    from src.orchestration.pipelines import dask_local

    assert dask_local is not None
