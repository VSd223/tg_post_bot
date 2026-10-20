import re
import json
from typing import List
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import MessageEntity
from database import db
from states import PostEditStates
from keyboards import (
    get_edit_post_choice_keyboard,
    get_post_edit_menu_keyboard,
    parse_buttons_syntax,
    build_inline_markup
)

edit_router = Router()

def deserialize_entities(entities_json: str) -> List[MessageEntity]:
    if not entities_json:
        return []
    try:
        data = json.loads(entities_json)
        return [MessageEntity(**item) for item in data]
    except Exception:
        return []

@edit_router.message(F.text == "✏️ Редактировать старый пост")
async def start_editing(message: types.Message):
    await message.answer(
        "Как вы хотите выбрать опубликованный пост для редактирования?",
        reply_markup=get_edit_post_choice_keyboard()
    )

@edit_router.callback_query(F.data == "edit_from_history")
async def list_recent_posts(callback: types.CallbackQuery, state: FSMContext):
    recent_posts = await db.get_recent_posts(callback.from_user.id, limit=10)
    if not recent_posts:
        await callback.answer("В базе данных бота еще нет опубликованных постов.", show_alert=True)
        return

    builder = types.InlineKeyboardMarkup(inline_keyboard=[])
    rows = []
    for post in recent_posts:
        title = (post['raw_text'][:20] + "...") if post['raw_text'] else f"Медиа ({post['content_type']})"
        rows.append([types.InlineKeyboardButton(text=f"[{post['channel_title']}] {title}", callback_data=f"select_post_{post['id']}")])

    rows.append([types.InlineKeyboardButton(text="⬅️ Отмена", callback_data="cancel_action")])
    builder.inline_keyboard = rows
    await callback.message.edit_text("Выберите пост для редактирования:", reply_markup=builder)

@edit_router.callback_query(F.data == "edit_from_link")
async def prompt_post_link(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PostEditStates.waiting_for_link)
    await callback.message.edit_text(
        "Отправьте ссылку на сообщение в канале.\n\n"
        "Форматы ссылок:\n"
        "• Публичный канал: <code>https://t.me/my_channel/123</code>\n"
        "• Закрытый канал: <code>https://t.me/c/1234567890/123</code>",
        parse_mode="HTML"
    )

@edit_router.message(PostEditStates.waiting_for_link)
async def process_post_link(message: types.Message, state: FSMContext):
    link = message.text.strip()
    public_match = re.search(r"t\.me/([a-zA-Z0-9_]+)/(\d+)", link)
    private_match = re.search(r"t\.me/c/(\d+)/(\d+)", link)

    chat_id = None
    message_id = None

    if private_match:
        chat_id = int(f"-100{private_match.group(1)}")
        message_id = int(private_match.group(2))
    elif public_match:
        chat_id = f"@{public_match.group(1)}"
        message_id = int(public_match.group(2))

    if not chat_id or not message_id:
        await message.answer("⚠️ Неверная ссылка на пост! Попробуйте еще раз.")
        return

    await state.update_data(
        edit_chat_id=chat_id,
        edit_message_id=message_id,
        edit_db_post_id=None
    )
    await state.set_state(PostEditStates.editing_menu)
    await message.answer(
        f"Пост найден (Канал: <code>{chat_id}</code>, ID: <code>{message_id}</code>).\nВыберите, что изменить:",
        parse_mode="HTML",
        reply_markup=get_post_edit_menu_keyboard(0)
    )

@edit_router.callback_query(F.data.startswith("select_post_"))
async def open_post_menu_from_db(callback: types.CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split("_")[2])
    post = await db.get_post_by_id(post_id)
    if not post:
        await callback.answer("Пост не найден в базе данных.", show_alert=True)
        return

    await state.update_data(
        edit_chat_id=post['channel_id'],
        edit_message_id=post['message_id'],
        edit_db_post_id=post['id'],
        content_type=post['content_type'],
        buttons_json=post['buttons_json']
    )
    await state.set_state(PostEditStates.editing_menu)
    await callback.message.edit_text(
        f"Пост #{post_id} готов к редактированию.\nВыберите действие:",
        reply_markup=get_post_edit_menu_keyboard(post_id)
    )

@edit_router.callback_query(PostEditStates.editing_menu, F.data.startswith("action_edit_text_"))
async def prompt_edit_text(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PostEditStates.waiting_for_new_text)
    await callback.message.answer("Отправьте новый текст поста (поддерживаются спойлеры, кастомные эмодзи и любое оформление):")
    await callback.answer()

@edit_router.message(PostEditStates.waiting_for_new_text)
async def perform_text_edit(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data["edit_chat_id"]
    message_id = data["edit_message_id"]
    db_post_id = data.get("edit_db_post_id")
    
    raw_text = message.text or message.caption or ""
    entities = message.entities or message.caption_entities or []
    serialized_entities = [e.model_dump() for e in entities]

    try:
        # Пытаемся отредактировать как текст сообщения
        try:
            await message.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=raw_text,
                entities=entities
            )
        except Exception:
            # Если это медиапост с подписью
            await message.bot.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=raw_text,
                caption_entities=entities
            )

        if db_post_id:
            await db.update_post_data(db_post_id, raw_text, json.dumps(serialized_entities), data.get("buttons_json", "[]"))

        await message.answer("✅ <b>Текст поста в канале мгновенно обновлен со всеми стилями!</b>", parse_mode="HTML")
        await state.clear()

    except Exception as e:
        await message.answer(f"❌ Ошибка обновления: {e}\nУбедитесь, что бот является администратором с правом редактирования сообщений.")

@edit_router.callback_query(PostEditStates.editing_menu, F.data.startswith("action_edit_buttons_"))
async def prompt_edit_buttons(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PostEditStates.waiting_for_new_buttons)
    await callback.message.answer(
        "Отправьте новые кнопки.\n\n"
        "Примеры:\n"
        "<code>Кнопка 1 - https://site.com | App - webapp:https://site.com</code>\n"
        "<code>Поделиться - share:Текст сообщения</code>\n"
        "<code>Инфо - alert:Всплывающий текст!</code>",
        parse_mode="HTML"
    )
    await callback.answer()

@edit_router.message(PostEditStates.waiting_for_new_buttons)
async def perform_buttons_edit(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data["edit_chat_id"]
    message_id = data["edit_message_id"]
    db_post_id = data.get("edit_db_post_id")

    buttons = parse_buttons_syntax(message.text)
    if not buttons:
        await message.answer("⚠️ Не удалось распознать кнопки. Проверьте правильность ссылок.")
        return

    markup = build_inline_markup(buttons)

    try:
        await message.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=markup
        )

        if db_post_id:
            post = await db.get_post_by_id(db_post_id)
            if post:
                await db.update_post_data(db_post_id, post['raw_text'], post['entities_json'], json.dumps(buttons))

        await message.answer("✅ <b>Кнопки у поста в канале успешно обновлены!</b>", parse_mode="HTML")
        await state.clear()

    except Exception as e:
        await message.answer(f"❌ Не удалось изменить кнопки: {e}")

@edit_router.callback_query(PostEditStates.editing_menu, F.data.startswith("action_remove_buttons_"))
async def perform_remove_buttons(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    chat_id = data["edit_chat_id"]
    message_id = data["edit_message_id"]
    db_post_id = data.get("edit_db_post_id")

    try:
        await callback.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=None
        )

        if db_post_id:
            post = await db.get_post_by_id(db_post_id)
            if post:
                await db.update_post_data(db_post_id, post['raw_text'], post['entities_json'], "[]")

        await callback.message.edit_text("✅ <b>Все кнопки удалены из поста в канале!</b>", parse_mode="HTML")
        await state.clear()

    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка удаления кнопок: {e}")

@edit_router.callback_query(F.data == "cancel_action")
async def cancel_generic_action(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Действие отменено.")