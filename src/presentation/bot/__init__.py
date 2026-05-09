"""Telegram-бот dcp_pipeline_bot для управления пайплайном distributed-churn-prediction.

Имя бота в Telegram: @dcp_pipeline_bot

Точка входа: ``python -m src.presentation.bot.main --profile <profile>``

Переменные окружения:
    TELEGRAM_BOT_TOKEN: токен бота, полученный от @BotFather (обязательно).

Структура модуля:
    main.py        — точка входа, инициализация бота и запуск polling
    handlers.py    — хендлеры команд (router)
    middlewares.py — ContainerMiddleware, AuthMiddleware
    messages.py    — текстовые константы MSG_*
    keyboards.py   — inline-клавиатуры
"""

BOT_NAME = "dcp_pipeline_bot"
