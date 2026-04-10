from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from src.churn.shared.exceptions import ConfigError


def find_project_root(start_path: Path | None = None) -> Path:
    """Ищет корень проекта, проверяя наличие папок configs/ и src/.

    Args:
        start_path (Path | None, optional): Путь к начальной точке для поиска корня проекта. По умолчанию None.

    Raises:
        ConfigError: Если корень проекта не найден.

    Returns:
        Path: Путь к корню проекта.
    """
    current = (start_path or Path.cwd()).resolve()

    for candidate in (current, *current.parents):
        if (candidate / "configs").exists() and (candidate / "src").exists():
            return candidate

    raise ConfigError("Не удалось найти корень проекта: ожидаются папки configs/ и src/")


def load_yaml(path: Path) -> dict[str, Any]:
    """Загружает YAML-файл и возвращает его содержимое в виде словаря.

    Args:
        path (Path): Путь к YAML-файлу.

    Returns:
        dict[str, Any]: Содержимое YAML-файла.

    Raises:
        ConfigError: Если файл не найден или его содержимое не является словарём.
    """
    if not path.exists():
        raise ConfigError(f"Файл конфига не найден: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    if not isinstance(data, dict):
        raise ConfigError(f"Конфиг должен быть YAML-словарём: {path}")

    return data


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Глубоко сливает два словаря, рекурсивно объединяя вложенные словари.

    Args:
        base (dict[str, Any]): Базовый словарь.
        override (dict[str, Any]): Словарь для переопределения значений.

    Returns:
        dict[str, Any]: Объединенный словарь.
    """

    result = deepcopy(base)

    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def load_settings_dict(project_root: Path, profile: str) -> dict[str, Any]:
    """Загружает и объединяет базовый и профильный конфиги.

    Args:
        project_root (Path): Путь к корню проекта.
        profile (str): Имя профиля (pandas | dask_local | dask_k8s).

    Returns:
        dict[str, Any]: Объединенный словарь настроек.
    """
    configs_dir = project_root / "configs"

    base_config = load_yaml(configs_dir / "base.yaml")
    profile_config = load_yaml(configs_dir / f"{profile}.yaml")

    return deep_merge(base_config, profile_config)