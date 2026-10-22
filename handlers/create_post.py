import json
from datetime import datetime, timedelta
from aiogram import Router, types, F
from typing import Optional
from aiogram.fsm.context import FSMContext
from database import db
from states import PostCreateStates
from keyboards import (
    get_post_preview_keyboard,
    parse_buttons_syntax,
    build_inline_markup,
    get_channels_keyboard,
    get_auto_delete_presets_keyboard
)
from scheduler import get_now_msk, format_datetime_msk, deserialize_entities, MSK_TZ

post_router = Router()

def parse_msk_datetime(user_input: str) -> datetime:
    """
    Парсер времени по МСК.
    Поддерживаемые форматы:
    18:30
    25.10 18:30
    25.10.2026 18:30
    """
    cleaned = user_input.strip().replace('/', '.').replace('-', '.')
    now = get_now_msk()

    # Формат HH:MM
    if len(cleaned.split()) == 1 and ':' in cleaned:
        time_part = datetime.strptime(cleaned, "%H:%M").time()
        target_dt = datetime.combine(now.date(), time_part, tzinfo=MSK_TZ)
        if target_dt <= now:
            target_dt += timedelta(days=1)
        return target_dt

    # Формат DD.MM HH:MM
    parts = cleaned.split()
    if len(parts) == 2:
        date_str, time_str = parts[0], parts[1]
        date_elements = date_str.split('.')
        if len(date_elements) == 2:
            date_str = f"{date_str}.{now.year}"
        
        full_dt_str = f"{date_str} {time_str}"
        dt = datetime.strptime(full_dt_str, "%d.%m.%Y %H:%M")
        return dt.replace(tzinfo=MSK_TZ)

    raise ValueError("Неверный формат даты и времени")

@post_router.message(F.text == "📝 Создать пост")
async def start_create_post(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(PostCreateStates.waiting_for_content)
    await message.answer(
        "📝 <b>Отправьте пост для публикации.</b>\n\n"
        "Поддерживается:\n"
        "• Текст с любым нативным форматированием (спойлеры, премиум-эмодзи, цитаты)\n"
        "• Фотография с текстом\n"
        "• Видео или GIF-анимация с текстом\n\n"
        "<i>Отправьте сообщение:</i>",
        parse_mode="HTML"
    )

@post_router.message(PostCreateStates.waiting_for_content)
async def process_post_content(message: types.Message, state: FSMContext):
    content_type = "text"
    file_id = None
    
    if message.photo:
        content_type = "photo"
        file_id = message.photo[-1].file_id
        raw_text = message.caption or ""
        entities = message.caption_entities or []
    elif message.video:
        content_type = "video"
        file_id = message.video.file_id
        raw_text = message.caption or ""
        entities = message.caption_entities or []
    elif message.animation:
        content_type = "animation"
        file_id = message.animation.file_id
        raw_text = message.caption or ""
        entities = message.caption_entities or []
    else:
        raw_text = message.text or ""
        entities = message.entities or []

    serialized_entities = [e.model_dump() for e in entities]

    await state.update_data(
        content_type=content_type,
        file_id=file_id,
        raw_text=raw_text,
        entities_json=json.dumps(serialized_entities),
        buttons_data=[]
    )
    await state.set_state(PostCreateStates.preview)
    await send_live_preview(message, state)

async def send_live_preview(message: types.Message, state: FSMContext):
    data = await state.get_data()
    content_type = data.get("content_type")
    raw_text = data.get("raw_text", "")
    file_id = data.get("file_id")
    buttons_data = data.get("buttons_data", [])
    entities = deserialize_entities(data.get("entities_json", "[]"))
    
    markup = build_inline_markup(buttons_data)

    await message.answer("👁️ <b>Предпросмотр поста:</b>", parse_mode="HTML")

    if content_type == "text":
        await message.bot.send_message(
            chat_id=message.chat.id,
            text=raw_text,
            entities=entities,
            reply_markup=markup
        )
    elif content_type == "photo":
        await message.bot.send_photo(
            chat_id=message.chat.id,
            photo=file_id,
            caption=raw_text,
            caption_entities=entities,
            reply_markup=markup
        )
    elif content_type == "video":
        await message.bot.send_video(
            chat_id=message.chat.id,
            video=file_id,
            caption=raw_text,
            caption_entities=entities,
            reply_markup=markup
        )
    elif content_type == "animation":
        await message.bot.send_animation(
            chat_id=message.chat.id,
            animation=file_id,
            caption=raw_text,
            caption_entities=entities,
            reply_markup=markup
        )

    await message.answer("⚙️ Выберите действие для поста:", reply_markup=get_post_preview_keyboard())

@post_router.callback_query(PostCreateStates.preview, F.data == "preview_edit_buttons")
async def prompt_buttons(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PostCreateStates.waiting_for_buttons)
    await callback.message.answer(
        "<b>🔘 Отправьте кнопки в формате:</b>\n\n"
        "<code>Ссылка - https://example.com | Приложение - webapp:https://site.com</code>\n"
        "<code>Репост - share:Текст | Всплывающее окно - alert:Текст уведомления</code>\n\n"
        "<i>Для удаления кнопок отправьте <code>0</code></i>",
        parse_mode="HTML"
    )
    await callback.answer()

@post_router.message(PostCreateStates.waiting_for_buttons)
async def process_buttons_input(message: types.Message, state: FSMContext):
    if message.text.strip() == "0":
        await state.update_data(buttons_data=[])
        await message.answer("Кнопки очищены.")
    else:
        buttons = parse_buttons_syntax(message.text)
        if not buttons:
            await message.answer("⚠️ Не удалось распознать кнопки. Проверьте правильность ссылок.")
            return
        await state.update_data(buttons_data=buttons)
        await message.answer("✅ Кнопки добавлены!")

    await state.set_state(PostCreateStates.preview)
    await send_live_preview(message, state)

@post_router.callback_query(PostCreateStates.preview, F.data == "preview_edit_text")
async def prompt_new_text(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PostCreateStates.waiting_for_new_text)
    await callback.message.answer("Отправьте новый текст (поддерживаются любые стили, спойлеры и эмодзи):")
    await callback.answer()

@post_router.message(PostCreateStates.waiting_for_new_text)
async def process_new_text(message: types.Message, state: FSMContext):
    raw_text = message.text or message.caption or ""
    entities = message.entities or message.caption_entities or []
    serialized_entities = [e.model_dump() for e in entities]

    await state.update_data(
        raw_text=raw_text,
        entities_json=json.dumps(serialized_entities)
    )
    await state.set_state(PostCreateStates.preview)
    await message.answer("✅ Текст обновлен.")
    await send_live_preview(message, state)

# --- МГНОВЕННАЯ ПУБЛИКАЦИЯ ---

@post_router.callback_query(PostCreateStates.preview, F.data == "preview_publish_now")
async def publish_now_choose_channel(callback: types.CallbackQuery, state: FSMContext):
    channels = await db.get_user_channels(callback.from_user.id)
    if not channels:
        await callback.answer("У вас нет добавленных каналов!", show_alert=True)
        return
    await state.set_state(PostCreateStates.selecting_channel_instant)
    await callback.message.edit_text("Выберите канал для моментальной публикации:", reply_markup=get_channels_keyboard(channels, prefix="pubnow_"))

@post_router.callback_query(PostCreateStates.selecting_channel_instant, F.data.startswith("pubnow_"))
async def instant_publish_channel_selected(callback: types.CallbackQuery, state: FSMContext):
    channel_id = int(callback.data.split("_")[1])
    await state.update_data(target_channel_id=channel_id, is_scheduled=False)
    await state.set_state(PostCreateStates.waiting_for_auto_delete)
    await callback.message.edit_text("Установить автоматическое удаление поста из канала?", reply_markup=get_auto_delete_presets_keyboard())

# --- ЗАПЛАНИРОВАННАЯ ПУБЛИКАЦИЯ ПО МСК ---

@post_router.callback_query(PostCreateStates.preview, F.data == "preview_schedule")
async def schedule_choose_channel(callback: types.CallbackQuery, state: FSMContext):
    channels = await db.get_user_channels(callback.from_user.id)
    if not channels:
        await callback.answer("У вас нет добавленных каналов!", show_alert=True)
        return
    await state.set_state(PostCreateStates.selecting_channel_schedule)
    await callback.message.edit_text("В какой канал запланировать отправку?", reply_markup=get_channels_keyboard(channels, prefix="schch_"))

@post_router.callback_query(PostCreateStates.selecting_channel_schedule, F.data.startswith("schch_"))
async def schedule_channel_selected(callback: types.CallbackQuery, state: FSMContext):
    channel_id = int(callback.data.split("_")[1])
    await state.update_data(target_channel_id=channel_id, is_scheduled=True)
    await state.set_state(PostCreateStates.waiting_for_publish_time)

    now_msk = get_now_msk().strftime("%H:%M")
    await callback.message.edit_text(
        f"🕒 Текущее время по МСК: <b>{now_msk}</b>\n\n"
        "<b>Введите дату и время публикации по Московскому времени:</b>\n\n"
        "Примеры:\n"
        "• <code>19:30</code> (сегодня или завтра в 19:30)\n"
        "• <code>25.10 14:00</code> (25 октября в 14:00)\n"
        "• <code>25.10.2026 14:00</code>",
        parse_mode="HTML"
    )

@post_router.message(PostCreateStates.waiting_for_publish_time)
async def process_schedule_time(message: types.Message, state: FSMContext):
    try:
        publish_dt = parse_msk_datetime(message.text)
        now_msk = get_now_msk()
        if publish_dt <= now_msk:
            await message.answer("⚠️ Время публикации уже прошло! Введите время в будущем.")
            return

        await state.update_data(publish_at_dt=publish_dt.isoformat())
        await state.set_state(PostCreateStates.waiting_for_auto_delete)
        await message.answer(
            f"📅 Публикация запланирована на <b>{publish_dt.strftime('%d.%m.%Y %H:%M')} (МСК)</b>.\n\n"
            "Установить таймер автоматического удаления поста из канала?",
            parse_mode="HTML",
            reply_markup=get_auto_delete_presets_keyboard()
        )
    except Exception:
        await message.answer("⚠️ Не удалось распознать время. Введите в формате <code>18:30</code> или <code>25.10 18:30</code>")

# --- ОБРАБОТКА АВТОУДАЛЕНИЯ И ФИНАЛИЗАЦИЯ ---

@post_router.callback_query(PostCreateStates.waiting_for_auto_delete, F.data.startswith("autodel_"))
async def process_autodelete_selection(callback: types.CallbackQuery, state: FSMContext):
    choice = callback.data.replace("autodel_", "")
    data = await state.get_data()
    is_scheduled = data.get("is_scheduled", False)
    
    # Расчет базового времени от которого отталкиваться
    if is_scheduled:
        base_dt = datetime.fromisoformat(data["publish_at_dt"])
    else:
        base_dt = get_now_msk()

    delete_dt = None

    if choice == "none":
        delete_dt = None
    elif choice == "1h":
        delete_dt = base_dt + timedelta(hours=1)
    elif choice == "24h":
        delete_dt = base_dt + timedelta(hours=24)
    elif choice == "48h":
        delete_dt = base_dt + timedelta(hours=48)
    elif choice == "custom":
        await state.set_state(PostCreateStates.waiting_for_custom_delete_time)
        await callback.message.edit_text(
            "Введите точную дату и время удаления по МСК (например, <code>26.10 18:00</code>):",
            parse_mode="HTML"
        )
        return

    await finalize_post(callback.message, state, delete_dt)

@post_router.message(PostCreateStates.waiting_for_custom_delete_time)
async def process_custom_delete_time(message: types.Message, state: FSMContext):
    data = await state.get_data()
    is_scheduled = data.get("is_scheduled", False)
    base_dt = datetime.fromisoformat(data["publish_at_dt"]) if is_scheduled else get_now_msk()

    try:
        del_dt = parse_msk_datetime(message.text)
        if del_dt <= base_dt:
            await message.answer("⚠️ Время удаления должно быть позже времени публикации!")
            return
        await finalize_post(message, state, del_dt)
    except Exception:
        await message.answer("⚠️ Неверный формат времени. Введите в формате <code>26.10 18:00</code>:")

async def finalize_post(event_message: types.Message, state: FSMContext, delete_dt: Optional[datetime]):
    data = await state.get_data()
    channel_id = data["target_channel_id"]
    content_type = data["content_type"]
    raw_text = data.get("raw_text", "")
    file_id = data.get("file_id")
    buttons_data = data.get("buttons_data", [])
    entities_json = data.get("entities_json", "[]")
    is_scheduled = data.get("is_scheduled", False)

    del_str = format_datetime_msk(delete_dt) if delete_dt else None

    if is_scheduled:
        publish_dt = datetime.fromisoformat(data["publish_at_dt"])
        pub_str = format_datetime_msk(publish_dt)

        await db.save_scheduled_post(
            user_id=event_message.chat.id,
            channel_id=channel_id,
            content_type=content_type,
            raw_text=raw_text,
            file_id=file_id,
            entities_json=entities_json,
            buttons_json=json.dumps(buttons_data),
            publish_at=pub_str,
            delete_at=del_str
        )

        del_info = f"\n🗑 Автоудаление: <b>{delete_dt.strftime('%d.%m.%Y %H:%M')} (МСК)</b>" if delete_dt else ""
        text = (
            "✅ <b>Пост успешно поставлен в очередь!</b>\n\n"
            f"📢 Канал ID: <code>{channel_id}</code>\n"
            f"⏰ Публикация: <b>{publish_dt.strftime('%d.%m.%Y %H:%M')} (МСК)</b>"
            f"{del_info}"
        )
        if isinstance(event_message, types.CallbackQuery):
            await event_message.message.edit_text(text, parse_mode="HTML")
        else:
            await event_message.answer(text, parse_mode="HTML")

    else:
        # Моментальная публикация
        entities = deserialize_entities(entities_json)
        markup = build_inline_markup(buttons_data)

        try:
            if content_type == "text":
                sent = await event_message.bot.send_message(channel_id, text=raw_text, entities=entities, reply_markup=markup)
            elif content_type == "photo":
                sent = await event_message.bot.send_photo(channel_id, photo=file_id, caption=raw_text, caption_entities=entities, reply_markup=markup)
            elif content_type == "video":
                sent = await event_message.bot.send_video(channel_id, video=file_id, caption=raw_text, caption_entities=entities, reply_markup=markup)
            elif content_type == "animation":
                sent = await event_message.bot.send_animation(channel_id, animation=file_id, caption=raw_text, caption_entities=entities, reply_markup=markup)

            await db.save_published_post(
                user_id=event_message.chat.id,
                channel_id=channel_id,
                message_id=sent.message_id,
                content_type=content_type,
                raw_text=raw_text,
                file_id=file_id,
                entities_json=entities_json,
                buttons_json=json.dumps(buttons_data),
                delete_at=del_str
            )

            del_info = f"\n🗑 Автоудаление сработает: <b>{delete_dt.strftime('%d.%m.%Y %H:%M')} (МСК)</b>" if delete_dt else ""
            await event_message.answer(f"🎉 <b>Пост опубликован прямо сейчас!</b>{del_info}", parse_mode="HTML")

        except Exception as e:
            await event_message.answer(f"❌ Ошибка отправки в канал: {e}")

    await state.clear()

@post_router.callback_query(F.data == "preview_cancel")
async def cancel_preview(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Действие отменено.")
