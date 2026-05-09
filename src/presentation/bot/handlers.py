from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from src.app.container import AppContainer
from src.presentation.bot.keyboards import profile_selection_keyboard
from src.presentation.bot.messages import (
    MSG_HELP,
    MSG_MODEL_INFO,
    MSG_NOT_IMPLEMENTED,
    MSG_PROFILES_LIST,
    MSG_SELECT_PROFILE,
    MSG_STATUS_NOT_FOUND,
    MSG_STATUS_TEMPLATE,
    MSG_WELCOME,
)

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
    """Обрабатывает команду /health. Проверяет состояние приложения.

    Args:
        message (Message): Входящее сообщение Telegram.
        container (AppContainer): Контейнер приложения, инжектированный middleware.
    """
    # TODO: вызвать health use case через container и вернуть результат
    # Пример:
    #   from src.application.use_cases.health import HealthUseCase
    #   result = HealthUseCase(container).execute()
    #   await message.answer(MSG_HEALTH_OK if result.ok else MSG_HEALTH_ERROR.format(error=result.error))
    container.logger.getChild("bot").debug("cmd_health: не реализован, user_id=%s", message.from_user and message.from_user.id)
    await message.answer(MSG_NOT_IMPLEMENTED)


@router.message(Command("profiles"))
async def cmd_profiles(message: Message, container: AppContainer) -> None:
    """Обрабатывает команду /profiles. Возвращает список доступных профилей.

    Args:
        message (Message): Входящее сообщение Telegram.
        container (AppContainer): Контейнер приложения, инжектированный middleware.
    """
    # TODO: получить список профилей из container.pipeline_registry и отформатировать
    # Пример:
    #   profiles = "\n".join(f"• {p}" for p in container.pipeline_registry.keys())
    #   await message.answer(MSG_PROFILES_LIST.format(profiles=profiles))
    _ = MSG_PROFILES_LIST
    container.logger.getChild("bot").debug("cmd_profiles: не реализован, user_id=%s", message.from_user and message.from_user.id)
    await message.answer(MSG_NOT_IMPLEMENTED)


@router.message(Command("run"))
async def cmd_run(message: Message) -> None:
    """Обрабатывает команду /run. Отображает inline-клавиатуру выбора профиля.

    Args:
        message (Message): Входящее сообщение Telegram.
    """
    await message.answer(MSG_SELECT_PROFILE, reply_markup=profile_selection_keyboard())


@router.callback_query(F.data.startswith("run:"))
async def cb_run_pipeline(callback: CallbackQuery, container: AppContainer) -> None:
    """Обрабатывает выбор профиля из inline-клавиатуры и запускает пайплайн.

    Получает профиль из ``callback.data`` (формат ``run:<profile>``),
    передаёт управление в пайплайн через AppContainer.

    Args:
        callback (CallbackQuery): Callback с выбранным профилем.
        container (AppContainer): Контейнер приложения, инжектированный middleware.

    Note:
        Для профиля ``dask_k8s`` требуется, чтобы бот был запущен внутри
        Kubernetes-кластера или Dask scheduler был доступен по сети
        (``tcp://dcp-cluster-service:8786``).
        При недоступности scheduler DaskK8sPipeline выбросит ``RuntimeError``
        — его нужно перехватить и отправить пользователю понятное сообщение.

        Для запуска dask_k8s-пайплайна необходимо пересоздать AppContainer
        с ``init_dask_client=True`` и профилем ``dask_k8s``, поскольку
        бот стартует с ``init_dask_client=False``.
    """
    profile: str = callback.data.split(":", 1)[1]  # "run:pandas" → "pandas"
    logger = container.logger.getChild("bot")
    logger.debug("cb_run_pipeline: profile=%s user_id=%s", profile, callback.from_user and callback.from_user.id)

    # TODO: запустить пайплайн через container
    # Общий шаблон (для pandas и dask_local):
    #
    #   pipeline = container.build_pipeline(run_options={"execute": True})
    #   result = await asyncio.to_thread(pipeline.run)
    #   run_id = result.get("run_id", "n/a")
    #   await callback.message.answer(MSG_PIPELINE_STARTED.format(run_id=run_id), parse_mode="HTML")
    #
    # Для dask_k8s — пересоздать контейнер с Dask client:
    #
    #   from src.app.bootstrap import bootstrap
    #   try:
    #       k8s_container = bootstrap(profile="dask_k8s", init_dask_client=True)
    #       pipeline = k8s_container.build_pipeline(run_options={"execute": True})
    #       result = await asyncio.to_thread(pipeline.run)
    #       run_id = result.get("run_id", "n/a")
    #       await callback.message.answer(MSG_PIPELINE_STARTED.format(run_id=run_id), parse_mode="HTML")
    #   except RuntimeError as exc:
    #       logger.error("Не удалось запустить dask_k8s pipeline: %s", exc)
    #       await callback.message.answer(
    #           "Dask scheduler недоступен. Убедитесь, что бот запущен "
    #           "внутри K8s-кластера или выполнен port-forward на порт 8786."
    #       )

    await callback.message.answer(MSG_NOT_IMPLEMENTED)
    await callback.answer()


@router.message(Command("status"))
async def cmd_status(message: Message, container: AppContainer) -> None:
    """Обрабатывает команду /status. Возвращает статус запуска пайплайна.

    Ожидает аргумент run_id: ``/status <run_id>``.

    Args:
        message (Message): Входящее сообщение Telegram.
        container (AppContainer): Контейнер приложения, инжектированный middleware.
    """
    # TODO: распарсить run_id из message.text, запросить статус через container
    # Пример:
    #   parts = (message.text or "").split(maxsplit=1)
    #   if len(parts) < 2:
    #       await message.answer("Использование: /status <run_id>")
    #       return
    #   run_id = parts[1].strip()
    #   run_store = FilePipelineRunStore(container.settings)
    #   run = run_store.get(run_id)
    #   if run is None:
    #       await message.answer(MSG_STATUS_NOT_FOUND.format(run_id=run_id), parse_mode="HTML")
    #       return
    #   await message.answer(MSG_STATUS_TEMPLATE.format(...), parse_mode="HTML")
    _ = MSG_STATUS_TEMPLATE
    _ = MSG_STATUS_NOT_FOUND
    container.logger.getChild("bot").debug("cmd_status: не реализован, user_id=%s", message.from_user and message.from_user.id)
    await message.answer(MSG_NOT_IMPLEMENTED)


@router.message(Command("model"))
async def cmd_model(message: Message, container: AppContainer) -> None:
    """Обрабатывает команду /model. Возвращает информацию об обученной модели.

    Args:
        message (Message): Входящее сообщение Telegram.
        container (AppContainer): Контейнер приложения, инжектированный middleware.
    """
    # TODO: получить метаданные модели через container и отформатировать ответ
    # Пример:
    #   settings = container.settings
    #   await message.answer(
    #       MSG_MODEL_INFO.format(name=settings.model.name, version=settings.model.version),
    #       parse_mode="HTML",
    #   )
    _ = MSG_MODEL_INFO
    container.logger.getChild("bot").debug("cmd_model: не реализован, user_id=%s", message.from_user and message.from_user.id)
    await message.answer(MSG_NOT_IMPLEMENTED)
