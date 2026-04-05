from src.churn.infrastructure.config.loader import find_project_root, load_config
from src.churn.infrastructure.logging.factory import get_logger

from src.churn.old_src.execution.backend import get_backend
from src.churn.old_src.execution.dask_client import create_client

from src.churn.pipeline.pandas_pipeline import PandasPipeline
from src.churn.pipeline.dask_pipeline import DaskPipeline


def main():
    PROJECT_ROOT = find_project_root()
    config = load_config(PROJECT_ROOT)

    logger = get_logger(
        name=__name__,
        log_dir=PROJECT_ROOT / config["paths"]["logs"],
        log_prefix="pipeline",
        level=config["logging"]["level"]
    )

    backend = get_backend(config, logger)
    client = create_client(config, logger)

    if backend == "pandas":
        pipeline = PandasPipeline(config, logger)

    else:
        pipeline = DaskPipeline(config, logger, client)

    pipeline.run()


if __name__ == "__main__":
    main()