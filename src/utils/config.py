from pathlib import Path
import yaml


def find_project_root(start_path: Path | None = None) -> Path:
    """Поиск корня проекта (директория где есть configs/)"""

    if start_path is None:
        start_path = Path.cwd()

    current = start_path.resolve()

    while current != current.parent:
        if (current / "configs").exists():
            return current
        current = current.parent

    raise FileNotFoundError("Не удалось найти папку configs/")


def load_config(project_root: Path) -> dict:
    """Загрузка конфигурации из YAML файла"""

    config_path = project_root / "configs" / "config.yaml"

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config
