from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """Строит и возвращает парсер аргументов командной строки для CLI приложения.
    Парсер поддерживает следующие команды:
    1. health - проверка bootstrap и текущего профиля
    2. show-config - показать объединённый конфиг
    3. run-pipeline - запустить pipeline или выполнить dry-run
    returns:
        argparse.ArgumentParser: Настроенный парсер аргументов.
    """
    parser = argparse.ArgumentParser(description="CLI для distributed-churn-prediction")

    subparsers = parser.add_subparsers(dest="command", required=True)

    health_parser = subparsers.add_parser(
        "health",
        help="Проверка bootstrap и текущего профиля",
    )
    health_parser.add_argument(
        "--profile",
        default="pandas",
        choices=["pandas", "dask_local", "dask_k8s"],
        help="Профиль конфигурации",
    )

    config_parser = subparsers.add_parser(
        "show-config",
        help="Показать объединённый конфиг",
    )
    config_parser.add_argument(
        "--profile",
        default="pandas",
        choices=["pandas", "dask_local", "dask_k8s"],
        help="Профиль конфигурации",
    )

    run_parser = subparsers.add_parser(
        "run-pipeline",
        help="Запустить pipeline или выполнить dry-run",
    )
    run_parser.add_argument(
        "--profile",
        default="pandas",
        choices=["pandas", "dask_local", "dask_k8s"],
        help="Профиль конфигурации",
    )
    run_parser.add_argument(
        "--execute",
        action="store_true",
        help="Реально выполнить pipeline.run(). Без флага будет dry-run.",
    )
    run_parser.add_argument(
        "--skip-load",
        action="store_true",
        help="Пропустить шаг загрузки датасета",
    )
    run_parser.add_argument(
        "--skip-features",
        action="store_true",
        help="Пропустить шаг feature engineering",
    )
    run_parser.add_argument(
        "--skip-train",
        action="store_true",
        help="Пропустить шаг обучения модели",
    )
    run_parser.add_argument(
        "--skip-eval",
        action="store_true",
        help="Пропустить шаг оценки модели",
    )

    return parser