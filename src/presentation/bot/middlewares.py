from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from src.app.container import AppContainer
from src.infrastructure.execution.local_pipeline_executor import BotPipelineExecutor
from src.infrastructure.pipeline_runs.file_store import FilePipelineRunStore
from src.presentation.bot.messages import MSG_UNAUTHORIZED


class ContainerMiddleware(BaseMiddleware):
    """Инжектирует AppContainer, FilePipelineRunStore и BotPipelineExecutor в data каждого хендлера.

    Добавляет ключи ``container``, ``run_store`` и ``executor`` в словарь data,
    что позволяет хендлерам объявить их как параметры и получать автоматически.

    Args:
        container (AppContainer): Инициализированный контейнер приложения.
        run_store (FilePipelineRunStore): Хранилище состояния pipeline runs.
        executor (BotPipelineExecutor): Долгоживущий executor для запуска и остановки pipeline.
    """

    def __init__(
        self,
        container: AppContainer,
        run_store: FilePipelineRunStore,
        executor: BotPipelineExecutor,
    ) -> None:
        self.container = container
        self.run_store = run_store
        self.executor = executor
        self.container.logger.getChild("bot.middleware").debug(
            "Инициализирован ContainerMiddleware: container_type=%s",
            type(container).__name__,
        )

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["container"] = self.container
        data["run_store"] = self.run_store
        data["executor"] = self.executor
        return await handler(event, data)


class AuthMiddleware(BaseMiddleware):
    """Ограничивает доступ к боту по списку разрешённых Telegram user_id.

    Если ``admin_chat_ids`` пуст — доступ разрешён всем пользователям.
    Если непуст — разрешён только тем, чей user_id присутствует в списке.
    Попытки несанкционированного доступа логируются с уровнем WARNING.

    Args:
        admin_chat_ids (list[int]): Список разрешённых Telegram user_id.
        logger (logging.Logger): Логгер для записи попыток несанкционированного доступа.
    """

    def __init__(self, admin_chat_ids: list[int], logger: logging.Logger) -> None:
        self._allowed: set[int] = set(admin_chat_ids)
        self._logger = logger
        self._logger.debug(
            "Инициализирован AuthMiddleware: admin_chat_ids=%s",
            list(self._allowed) if self._allowed else "не ограничено",
        )

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not self._allowed:
            return await handler(event, data)

        user_id: int | None = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id is not None and user_id not in self._allowed:
            self._logger.warning(
                "Несанкционированный доступ: user_id=%s", user_id
            )
            if isinstance(event, Message):
                await event.answer(MSG_UNAUTHORIZED)
            elif isinstance(event, CallbackQuery):
                await event.answer(MSG_UNAUTHORIZED, show_alert=True)
            return

        return await handler(event, data)
