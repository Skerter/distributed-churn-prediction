"""Asyncio-мониторинг pipeline run и push-уведомления через Telegram Bot API.

Не содержит логики запуска пайплайна — только ожидание завершения треда
и отправка уведомлений пользователю.
"""
from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable

from aiogram import Bot

from src.infrastructure.pipeline_runs.file_store import FilePipelineRunStore
from src.presentation.bot.messages import (
    MSG_PIPELINE_DONE,
    MSG_PIPELINE_FAILED,
    MSG_PIPELINE_TIMEOUT,
)


async def watch_and_notify(
    *,
    run_id: str,
    thread: threading.Thread,
    cancel_event: threading.Event,
    chat_id: int,
    bot: Bot,
    run_store: FilePipelineRunStore,
    logger,
    timeout_seconds: int,
    on_done: Callable[[str], None],
) -> None:
    """Ждёт завершения pipeline треда и отправляет push-уведомление пользователю.

    Args:
        run_id: Идентификатор pipeline run.
        thread: Рабочий тред BotPipelineExecutor.
        cancel_event: Event для сигнализации треду об отмене по таймауту.
        chat_id: Telegram chat_id для отправки уведомления.
        bot: Aiogram Bot instance.
        run_store: Хранилище состояний pipeline runs.
        logger: Logger от bot-хендлера.
        timeout_seconds: Максимальное время ожидания в секундах.
        on_done: Callback для освобождения ресурсов (executor.cleanup).
    """
    loop = asyncio.get_running_loop()
    logger.debug("watch_and_notify: начало мониторинга run_id=%s timeout=%ds", run_id, timeout_seconds)

    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, thread.join),
            timeout=float(timeout_seconds),
        )
    except asyncio.TimeoutError:
        cancel_event.set()
        run_store.mark_failed(run_id, error=f"Таймаут: превышен лимит {timeout_seconds}s")
        logger.warning(
            "watch_and_notify: pipeline run прерван по таймауту run_id=%s", run_id
        )
        on_done(run_id)
        await bot.send_message(
            chat_id,
            MSG_PIPELINE_TIMEOUT.format(run_id=run_id),
            parse_mode="HTML",
        )
        return
    except Exception as exc:
        logger.exception(
            "watch_and_notify: неожиданная ошибка при мониторинге run_id=%s: %s",
            run_id,
            exc,
        )
        on_done(run_id)
        return

    on_done(run_id)
    logger.debug("watch_and_notify: тред завершён run_id=%s", run_id)

    try:
        payload = run_store.get(run_id)
    except FileNotFoundError:
        logger.error(
            "watch_and_notify: run_id=%s не найден в store после завершения треда",
            run_id,
        )
        return

    status = payload.get("status")

    if status == "succeeded":
        duration = (payload.get("result") or {}).get("duration_seconds", "?")
        logger.info("watch_and_notify: pipeline succeeded run_id=%s duration=%s", run_id, duration)
        await bot.send_message(
            chat_id,
            MSG_PIPELINE_DONE.format(run_id=run_id, duration=duration),
            parse_mode="HTML",
        )
    else:
        error = payload.get("error") or "неизвестная ошибка"
        logger.info(
            "watch_and_notify: pipeline failed run_id=%s error=%s", run_id, error
        )
        await bot.send_message(
            chat_id,
            MSG_PIPELINE_FAILED.format(run_id=run_id, error=error),
            parse_mode="HTML",
        )
