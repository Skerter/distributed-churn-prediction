from __future__ import annotations

import json
import sys

from src.app.bootstrap import bootstrap
from src.application.dto.requests import RunPipelineRequest
from src.application.use_cases.get_health import get_health
from src.application.use_cases.execute_pipeline import run_pipeline
from src.infrastructure.execution.dask_client import close_dask_client
from src.presentation.cli.parser import build_parser


def main() -> int:
    """Главная функция CLI приложения для управления ML pipeline.

    Returns:
        int: Код завершения процесса (0 - успех, 1 - ошибка).
    """
    parser = build_parser()
    args = parser.parse_args()

    container = None

    try:
        # BUG: Запуск в режиме dry-run с профилем dask_k8s может привести к ошибкам из-за невозможности подключения к кластеру. Рекомендуется использовать профиль dask_local для dry-run.
        if args.command == "run-pipeline" and args.profile == "dask_k8s" and not args.execute:
            print("[WARNING] Запуск в режиме dry-run с профилем dask_k8s может привести к ошибкам из-за невозможности подключения к кластеру. Рекомендуется использовать профиль dask_local для dry-run.",
                  file=sys.stderr)

        container = bootstrap(profile=args.profile)

        if args.command == "health":
            response = get_health(container)
            print(json.dumps(response.to_dict(), indent=2, ensure_ascii=False))
            return 0

        if args.command == "show-config":
            print(
                json.dumps(
                    container.settings.to_dict(),
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0

        if args.command == "run-pipeline":
            request = RunPipelineRequest(
                profile=args.profile,
                execute=args.execute,
                skip_load=args.skip_load,
                skip_features=args.skip_features,
                skip_train=args.skip_train,
                skip_eval=args.skip_eval,
            )
            response = run_pipeline(container, request)
            print(json.dumps(response.to_dict(), indent=2, ensure_ascii=False))
            return 0

        parser.print_help()
        return 1

    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    finally:
        if container is not None:
            close_dask_client(container.dask_client, container.logger)


if __name__ == "__main__":
    raise SystemExit(main())