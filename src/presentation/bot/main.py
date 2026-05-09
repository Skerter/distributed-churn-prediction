from __future__ import annotations

import argparse
import asyncio
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from src.app.bootstrap import bootstrap
from src.infrastructure.execution.dask_client import close_dask_client
from src.presentation.bot.handlers import router
from src.presentation.bot.middlewares import AuthMiddleware, ContainerMiddleware


def _build_parser() -> argparse.ArgumentParser:
    """Строит парсер аргументов командной строки для Telegram-бота.

    Returns:
        argparse.ArgumentParser: Настроенный парсер аргументов.
    """
    parser = argparse.ArgumentParser(
        description="Telegram-бот для управления пайплайном distributed-churn-prediction."
    )
    parser.add_argument(
        "--profile",
        choices=["pandas", "dask_local", "dask_k8s"],
        default="pandas",
        help=(
            "Профиль конфигурации приложения (default: pandas). "
            "Определяет настройки приложения, которые бот использует при старте. "
            "Dask client при старте не создаётся — он инициализируется внутри "
            "хендлера /run в момент запуска пайплайна."
        ),
    )
    return parser


async def _run_bot(token: str, profile: str) -> None:
    """Инициализирует AppContainer, регистрирует middleware и запускает long-polling.

    Args:
        token (str): Telegram Bot API token.
        profile (str): Профиль конфигурации для bootstrap.

    Raises:
        Exception: Любое необработанное исключение при старте или в процессе polling.
    """
    # Dask client не создаётся при старте бота — соединение устанавливается
    # внутри хендлера cb_run_pipeline непосредственно перед запуском пайплайна,
    # чтобы избежать долгого и потенциально неудачного коннекта при инициализации.
    container = bootstrap(profile=profile, init_dask_client=False)
    logger = container.logger.getChild("bot")

    logger.info(
        "Telegram bot запущен: profile=%s mode=%s",
        profile,
        container.settings.runtime.mode.value,
    )

    admin_ids = container.settings.bot.admin_chat_ids
    if admin_ids:
        logger.info("Доступ ограничен: admin_chat_ids=%s", admin_ids)
    else:
        logger.info("Доступ открыт для всех пользователей")

    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())

    container_mw = ContainerMiddleware(container)
    auth_mw = AuthMiddleware(admin_ids, logger.getChild("auth"))

    dp.message.middleware(container_mw)
    dp.message.middleware(auth_mw)
    dp.callback_query.middleware(container_mw)
    dp.callback_query.middleware(auth_mw)

    dp.include_router(router)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        close_dask_client(container.dask_client, logger)
        logger.info("Telegram bot остановлен")


def main() -> int:
    """Точка входа Telegram-бота.

    Читает токен из переменной окружения ``TELEGRAM_BOT_TOKEN``,
    инициализирует AppContainer через bootstrap, регистрирует middleware
    и запускает long-polling.

    Returns:
        int: Код завершения процесса (0 - успех, 1 - ошибка).
    """
    parser = _build_parser()
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print(
            "[ERROR] Переменная окружения TELEGRAM_BOT_TOKEN не задана или пуста.",
            file=sys.stderr,
        )
        return 1

    try:
        asyncio.run(_run_bot(token=token, profile=args.profile))
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
