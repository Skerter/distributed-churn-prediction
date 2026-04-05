from dataclasses import dataclass

@dataclass
class AppContext:
    settings: Settings
    logger: logging.Logger
    backend: ExecutionBackend
    project_root: Path

def bootstrap(profile: str) -> AppContext:
    project_root = resolve_project_root()
    settings = load_settings(project_root, profile)
    logger = build_logger(settings, project_root)
    backend = build_backend(settings, logger)

    return AppContext(
        settings=settings,
        logger=logger,
        backend=backend,
        project_root=project_root,
    )

def main():
    args = parse_args()
    ctx = bootstrap(args.profile)
    TrainPipeline(ctx).run()