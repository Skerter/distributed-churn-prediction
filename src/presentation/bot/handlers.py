from __future__ import annotations

import asyncio

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from src.app.container import AppContainer
from src.application.dto.requests import CreatePipelineRunRequest
from src.application.use_cases.get_health import get_health
from src.application.use_cases.get_model_info import get_model_info
from src.application.use_cases.list_profiles import list_profiles
from src.infrastructure.execution.pipeline_executor_factory import build_bot_pipeline_executor
from src.infrastructure.pipeline_runs.file_store import FilePipelineRunStore
from src.presentation.bot.keyboards import profile_selection_keyboard
from src.presentation.bot.messages import (
    MSG_ASK_RUN_ID,
    MSG_HEALTH_OK,
    MSG_HELP,
    MSG_MODEL_INFO,
    MSG_PIPELINE_BUSY,
    MSG_PIPELINE_ERROR,
    MSG_PIPELINE_STARTED,
    MSG_PROFILES_LIST,
    MSG_SELECT_PROFILE,
    MSG_STATUS_CANCELLED,
    MSG_STATUS_NOT_FOUND,
    MSG_STATUS_TEMPLATE,
    MSG_WELCOME,
)
from src.presentation.bot.runner import watch_and_notify

_STATUS_LABELS: dict[str, str] = {
    "queued": "В очереди",
    "running": "Выполняется",
    "succeeded": "Успешно завершён",
    "failed": "Завершён с ошибкой",
}


class StatusFlow(StatesGroup):
    """Состояния диалога команды /status."""

    waiting_for_run_id = State()


router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Обрабатывает команду /start. Отправляет приветственное сообщение.

    Args:
        message (Message): Входящее сообщение Telegram.
    """
    await message.answer(MSG_WELCOME)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Обрабатывает команду /help. Возвращает список доступных команд.

    Args:
        message (Message): Входящее сообщение Telegram.
    """
    await message.answer(MSG_HELP, parse_mode="HTML")


@router.message(Command("health"))
async def cmd_health(message: Message, container: AppContainer) -> None:
    """Обрабатывает команду /health. Возвращает состояние приложения.

    Args:
        message (Message): Входящее сообщение Telegram.
        container (AppContainer): Контейнер приложения, инжектированный middleware.
    """
    result = get_health(container)
    await message.answer(
        MSG_HEALTH_OK.format(
            app_name=result.app_name,
            app_version=result.app_version,
            profile_mode=result.profile_mode,
            backend=result.backend,
        ),
        parse_mode="HTML",
    )


@router.message(Command("profiles"))
async def cmd_profiles(message: Message) -> None:
    """Обрабатывает команду /profiles. Возвращает список доступных профилей.

    Args:
        message (Message): Входящее сообщение Telegram.
    """
    result = list_profiles()
    lines = []
    for p in result.profiles:
        header = f"<b>{p.name}</b>"
        if p.name == result.default_profile:
            header += " (по умолчанию)"
        lines.append(f"{header}\n{p.description}")
        if p.warning:
            lines.append(f"<i>Внимание: {p.warning}</i>")
    await message.answer(
        MSG_PROFILES_LIST.format(profiles="\n\n".join(lines)),
        parse_mode="HTML",
    )


@router.message(Command("run"))
async def cmd_run(message: Message) -> None:
    """Обрабатывает команду /run. Отображает inline-клавиатуру выбора профиля.

    Args:
        message (Message): Входящее сообщение Telegram.
    """
    await message.answer(MSG_SELECT_PROFILE, reply_markup=profile_selection_keyboard())


@router.callback_query(F.data.startswith("run:"))
async def cb_run_pipeline(
    callback: CallbackQuery,
    container: AppContainer,
    run_store: FilePipelineRunStore,
) -> None:
    """Запускает пайплайн в фоне для выбранного профиля.

    Получает профиль из ``callback.data`` (формат ``run:<profile>``),
    создаёт pipeline run запись и запускает выполнение в отдельном потоке.
    Пользователь немедленно получает run_id для отслеживания прогресса
    через /status.

    Args:
        callback (CallbackQuery): Callback с выбранным профилем.
        container (AppContainer): Контейнер приложения, инжектированный middleware.
        run_store (FilePipelineRunStore): Хранилище pipeline runs, инжектированное middleware.

    Note:
        Для профиля ``dask_k8s`` требуется, чтобы бот был запущен внутри
        Kubernetes-кластера или Dask scheduler был доступен по сети
        (``tcp://dcp-cluster-service:8786``). При недоступности scheduler
        pipeline run создастся со статусом FAILED — результат виден через /status.
    """
    profile: str = callback.data.split(":", 1)[1]
    logger = container.logger.getChild("bot")
    logger.debug(
        "cb_run_pipeline: profile=%s user_id=%s",
        profile,
        callback.from_user and callback.from_user.id,
    )

    await callback.answer()

    executor = build_bot_pipeline_executor(container=container, store=run_store)
    chat_id = callback.from_user.id
    timeout = container.settings.bot.pipeline_timeout_seconds

    try:
        payload = executor.submit(CreatePipelineRunRequest(execute=True), chat_id=chat_id)
    except RuntimeError as exc:
        if "активный pipeline run" in str(exc):
            await callback.message.answer(MSG_PIPELINE_BUSY)
        else:
            logger.error(
                "Не удалось запустить pipeline: profile=%s error=%s", profile, exc
            )
            await callback.message.answer(MSG_PIPELINE_ERROR.format(error=exc))
        return

    run_id = payload["run_id"]
    asyncio.create_task(
        watch_and_notify(
            run_id=run_id,
            thread=executor.get_thread(run_id),
            cancel_event=executor.get_cancel_event(run_id),
            chat_id=chat_id,
            bot=callback.bot,
            run_store=run_store,
            logger=logger,
            timeout_seconds=timeout,
            on_done=executor.cleanup,
        )
    )

    await callback.message.answer(
        MSG_PIPELINE_STARTED.format(run_id=run_id),
        parse_mode="HTML",
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Отменяет текущий активный диалог (например, ожидание run_id).

    Args:
        message (Message): Входящее сообщение Telegram.
        state (FSMContext): Контекст FSM текущего пользователя.
    """
    await state.clear()
    await message.answer(MSG_STATUS_CANCELLED)


@router.message(Command("status"))
async def cmd_status(message: Message, state: FSMContext) -> None:
    """Обрабатывает команду /status. Запрашивает run_id в интерактивном диалоге.

    Переводит пользователя в состояние ``StatusFlow.waiting_for_run_id``
    и просит ввести run_id отдельным сообщением.

    Args:
        message (Message): Входящее сообщение Telegram.
        state (FSMContext): Контекст FSM текущего пользователя.
    """
    await state.set_state(StatusFlow.waiting_for_run_id)
    await message.answer(MSG_ASK_RUN_ID, parse_mode="HTML")


@router.message(StatusFlow.waiting_for_run_id)
async def process_status_run_id(
    message: Message,
    state: FSMContext,
    container: AppContainer,
    run_store: FilePipelineRunStore,
) -> None:
    """Принимает run_id и возвращает статус запуска.

    Вызывается автоматически когда пользователь находится в состоянии
    ``StatusFlow.waiting_for_run_id`` и присылает любое сообщение.

    Args:
        message (Message): Сообщение с run_id от пользователя.
        state (FSMContext): Контекст FSM — очищается после обработки.
        container (AppContainer): Контейнер приложения, инжектированный middleware.
        run_store (FilePipelineRunStore): Хранилище pipeline runs, инжектированное middleware.
    """
    await state.clear()

    run_id = (message.text or "").strip()
    logger = container.logger.getChild("bot")
    logger.debug(
        "process_status_run_id: run_id=%s user_id=%s",
        run_id,
        message.from_user and message.from_user.id,
    )

    if not run_id:
        await message.answer("run_id не может быть пустым. Попробуй ещё раз: /status")
        return

    try:
        payload = await asyncio.to_thread(run_store.get, run_id)
    except FileNotFoundError:
        await message.answer(MSG_STATUS_NOT_FOUND.format(run_id=run_id), parse_mode="HTML")
        return

    status_raw = payload.get("status", "—")
    text = MSG_STATUS_TEMPLATE.format(
        run_id=run_id,
        status=_STATUS_LABELS.get(status_raw, status_raw),
        profile=payload.get("profile", "—"),
        started_at=payload.get("started_at") or "—",
        finished_at=payload.get("finished_at") or "—",
    )

    if payload.get("error"):
        text += f"\n\nОшибка: <code>{payload['error']}</code>"

    await message.answer(text, parse_mode="HTML")


@router.message(Command("model"))
async def cmd_model(message: Message, container: AppContainer) -> None:
    """Обрабатывает команду /model. Возвращает информацию об обученной модели.

    Args:
        message (Message): Входящее сообщение Telegram.
        container (AppContainer): Контейнер приложения, инжектированный middleware.
    """
    profile = container.settings.runtime.mode.value
    result = get_model_info(container, profile=profile)

    model_exists = "файл найден" if result.model.get("exists") else "файл не найден"

    if result.metrics:
        metrics_lines = [
            f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}"
            for k, v in result.metrics.items()
        ]
        metrics_text = "\n".join(metrics_lines)
    else:
        metrics_text = "  нет данных"

    await message.answer(
        MSG_MODEL_INFO.format(
            name=result.model["name"],
            version=result.model["version"],
            mode=result.mode,
            backend=result.backend,
            filename=result.model["expected_filename"],
            exists=model_exists,
            metrics=metrics_text,
        ),
        parse_mode="HTML",
    )
