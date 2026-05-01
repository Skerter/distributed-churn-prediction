from __future__ import annotations

from src.shared.enums import BackendKind, RuntimeMode #TODO: Unused BackendKind
from src.shared.exceptions import RuntimeModeError


def resolve_backend(mode: RuntimeMode) -> BackendKind:
    """Определяет тип бекэнда на основе заданного режима выполнения.

    Args:
        mode (RuntimeMode): Режим выполнения приложения, определяющий выбор бекэнда.

    Returns:
        BackendKind: Тип бекэнда, соответствующий заданному режиму выполнения.

    Raises:
        RuntimeModeError: Если задан неизвестный режим выполнения.
    """
    if mode == RuntimeMode.PANDAS:
        return BackendKind.LOCAL

    if mode in (RuntimeMode.DASK_LOCAL, RuntimeMode.DASK_K8S):
        return BackendKind.DASK

    raise RuntimeModeError(f"Неизвестный runtime mode: {mode}")