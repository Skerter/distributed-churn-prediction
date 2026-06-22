import pytest


@pytest.mark.smoke
def test_import_train_service():
    from src.application.services import train_service

    assert train_service is not None


@pytest.mark.smoke
def test_import_feature_service():
    from src.application.services import feature_service

    assert feature_service is not None


@pytest.mark.smoke
def test_import_pipeline_module():
    from src.orchestration.pipelines import dask_local

    assert dask_local is not None
