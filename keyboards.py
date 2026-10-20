import re
import json
from typing import List, Dict, Optional
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Создать пост")],
            [KeyboardButton(text="⏰ Запланированные посты"), KeyboardButton(text="📢 Мои каналы")],
            [KeyboardButton(text="✏️ Редактировать старый пост"), KeyboardButton(text="ℹ️ Помощь по кнопкам")]
        ],
        resize_keyboard=True
    )

def parse_buttons_syntax(text: str) -> List[List[Dict[str, str]]]:
    result = []
    lines = text.strip().split('\n')
    
    for line in lines:
        if not line.strip():
            continue
        row = []
        raw_buttons = line.split('|')
        for raw_btn in raw_buttons:
            parts = re.split(r'\s*-\s*|\s*=\s*', raw_btn.strip(), maxsplit=1)
            if len(parts) == 2:
                btn_name = parts[0].strip()
                target = parts[1].strip()

                if target.startswith("webapp:"):
                    url = target.replace("webapp:", "", 1).strip()
                    if url.startswith(("http://", "https://")):
                        row.append({"type": "webapp", "text": btn_name, "data": url})
                
                elif target.startswith("share:"):
                    query = target.replace("share:", "", 1).strip()
                    row.append({"type": "share", "text": btn_name, "data": query})

                elif target.startswith("alert:"):
                    alert_text = target.replace("alert:", "", 1).strip()
                    row.append({"type": "alert", "text": btn_name, "data": alert_text[:200]})

                elif target.startswith(("http://", "https://", "tg://")):
                    row.append({"type": "url", "text": btn_name, "data": target})

        if row:
            result.append(row)
    return result

def build_inline_markup(buttons_data: Optional[List[List[Dict[str, str]]]]) -> Optional[InlineKeyboardMarkup]:
    if not buttons_data:
        return None

    builder = InlineKeyboardBuilder()
    for row in buttons_data:
        row_buttons = []
        for btn in row:
            b_type = btn.get("type", "url")
            b_text = btn.get("text", "Кнопка")
            b_data = btn.get("data", "")

            if b_type == "url":
                row_buttons.append(InlineKeyboardButton(text=b_text, url=b_data))
            elif b_type == "webapp":
                row_buttons.append(InlineKeyboardButton(text=b_text, web_app=WebAppInfo(url=b_data)))
            elif b_type == "share":
                row_buttons.append(InlineKeyboardButton(text=b_text, switch_inline_query=b_data))
            elif b_type == "alert":
                row_buttons.append(InlineKeyboardButton(text=b_text, callback_data=f"al:{b_data[:50]}"))

        if row_buttons:
            builder.row(*row_buttons)
            
    return builder.as_markup()

def get_post_preview_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔘 Добавить / Сменить кнопки", callback_data="preview_edit_buttons"),
        InlineKeyboardButton(text="✍️ Изменить текст", callback_data="preview_edit_text")
    )
    builder.row(
        InlineKeyboardButton(text="🚀 Опубликовать сейчас", callback_data="preview_publish_now"),
        InlineKeyboardButton(text="⏰ Запланировать (МСК)", callback_data="preview_schedule")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="preview_cancel")
    )
    return builder.as_markup()

def get_channels_keyboard(channels: List[Dict], prefix: str = "send_to_") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ch in channels:
        builder.row(InlineKeyboardButton(text=f"📢 {ch['title']}", callback_data=f"{prefix}{ch['channel_id']}"))
    builder.row(InlineKeyboardButton(text="⬅️ Отмена", callback_data="preview_cancel"))
    return builder.as_markup()

def get_auto_delete_presets_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❌ Не удалять", callback_data="autodel_none"),
        InlineKeyboardButton(text="⏱ 1 час", callback_data="autodel_1h")
    )
    builder.row(
        InlineKeyboardButton(text="⏱ 24 часа", callback_data="autodel_24h"),
        InlineKeyboardButton(text="⏱ 48 часов", callback_data="autodel_48h")
    )
    builder.row(
        InlineKeyboardButton(text="✍️ Задать точное время (МСК)", callback_data="autodel_custom")
    )
    return builder.as_markup()

def get_edit_post_choice_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📋 Выбрать из истории", callback_data="edit_from_history"))
    builder.row(InlineKeyboardButton(text="🔗 Ввести ссылку на пост", callback_data="edit_from_link"))
    builder.row(InlineKeyboardButton(text="⬅️ Отмена", callback_data="cancel_action"))
    return builder.as_markup()

def get_post_edit_menu_keyboard(post_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 Изменить текст", callback_data=f"action_edit_text_{post_id}"),
        InlineKeyboardButton(text="🔘 Изменить кнопки", callback_data=f"action_edit_buttons_{post_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить кнопки", callback_data=f"action_remove_buttons_{post_id}"),
        InlineKeyboardButton(text="⬅️ Завершить", callback_data="cancel_action")
    )
    return builder.as_markup()