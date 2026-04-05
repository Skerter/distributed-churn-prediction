from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from src.churn.shared.exceptions import ConfigError


def find_project_root(start_path: Path | None = None) -> Path:
    '''Ищет корень проекта, проверяя наличие папок configs/ и src/.
    params:
        - start_path: начальная точка для поиска корня проекта. Если None, используется текущая директория.
    returns:
        - Path: путь к корню проекта.
    raises:
        - ConfigError: если корень проекта не найден.'''
    current = (start_path or Path.cwd()).resolve()

    for candidate in (current, *current.parents):
        if (candidate / "configs").exists() and (candidate / "src").exists():
            return candidate

    raise ConfigError("Не удалось найти корень проекта: ожидаются папки configs/ и src/")


def load_yaml(path: Path) -> dict[str, Any]:
    '''Загружает YAML-файл и возвращает его содержимое в виде словаря.
    params:
        - path: путь к YAML-файлу.
    returns:
        - dict[str, Any]: содержимое YAML-файла.
    raises:
        - ConfigError: если файл не найден или его содержимое не является словарём.'''
    if not path.exists():
        raise ConfigError(f"Файл конфига не найден: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    if not isinstance(data, dict):
        raise ConfigError(f"Конфиг должен быть YAML-словарём: {path}")

    return data


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    '''Глубоко сливает два словаря, рекурсивно объединяя вложенные словари.
    params:
        - base: базовый словарь.
        - override: словарь для переопределения значений.
    returns:
        - dict[str, Any]: объединенный словарь.'''
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
    '''Загружает и объединяет базовый и профильный конфиги.
    params:
        - project_root: путь к корню проекта.
        - profile: имя профиля (pandas | dask_local | dask_k8s).
    returns:
        - dict[str, Any]: объединенный словарь настроек.'''
    configs_dir = project_root / "configs"

    base_config = load_yaml(configs_dir / "base.yaml")
    profile_config = load_yaml(configs_dir / f"{profile}.yaml")

    return deep_merge(base_config, profile_config)