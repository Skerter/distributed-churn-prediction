from src.utils.config import find_project_root, load_config
from src.utils.logger import get_logger

from src.execution.backend import get_backend
from src.execution.dask_client import create_client

from src.pipeline.pandas_pipeline import PandasPipeline
from src.pipeline.dask_pipeline import DaskPipeline


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