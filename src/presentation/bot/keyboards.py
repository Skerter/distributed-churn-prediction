from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def profile_selection_keyboard() -> InlineKeyboardMarkup:
    """Строит inline-клавиатуру для выбора профиля пайплайна.

    Каждая кнопка передаёт ``callback_data`` вида ``run:<profile>``,
    который обрабатывается в ``cb_run_pipeline``.

    Returns:
        InlineKeyboardMarkup: Клавиатура с тремя кнопками профилей.
    """
    buttons = [
        [
            InlineKeyboardButton(text="pandas", callback_data="run:pandas"),
            InlineKeyboardButton(text="dask_local", callback_data="run:dask_local"),
            InlineKeyboardButton(text="dask_k8s", callback_data="run:dask_k8s"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
