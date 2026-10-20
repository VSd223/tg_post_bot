from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import db
from states import ChannelStates

channels_router = Router()

@channels_router.message(F.text == "📢 Мои каналы")
async def list_channels(message: types.Message):
    user_channels = await db.get_user_channels(message.from_user.id)
    builder = InlineKeyboardBuilder()
    
    if not user_channels:
        text = "У вас пока нет подключенных каналов."
    else:
        text = "<b>Подключенные каналы:</b>\n\n"
        for ch in user_channels:
            uname = f"(@{ch['username']})" if ch['username'] else ""
            text += f"• <b>{ch['title']}</b> {uname}\n"
            builder.row(types.InlineKeyboardButton(text=f"❌ Отвязать {ch['title'][:15]}", callback_data=f"del_channel_{ch['channel_id']}"))

    builder.row(types.InlineKeyboardButton(text="➕ Добавить канал", callback_data="add_channel"))
    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())

@channels_router.callback_query(F.data == "add_channel")
async def prompt_add_channel(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ChannelStates.waiting_for_channel)
    text = (
        "<b>Шаги для привязки канала:</b>\n\n"
        "1. Добавьте этого бота в администраторы вашего канала с правами:\n"
        "   — <i>Публикация сообщений</i>\n"
        "   — <i>Редактирование сообщений</i>\n"
        "2. <b>Перешлите сюда любое сообщение из этого канала</b> или отправьте его ID / @username канала."
    )
    await callback.message.edit_text(text, parse_mode="HTML")

@channels_router.message(ChannelStates.waiting_for_channel)
async def process_channel_input(message: types.Message, state: FSMContext):
    chat_id = None

    if message.forward_from_chat and message.forward_from_chat.type == "channel":
        chat_id = message.forward_from_chat.id
    else:
        raw_text = message.text.strip()
        if raw_text.startswith("@") or raw_text.startswith("-100") or raw_text.lstrip('-').isdigit():
            chat_id = int(raw_text) if raw_text.lstrip('-').isdigit() else raw_text

    if not chat_id:
        await message.answer("⚠️ Не удалось определить канал. Перешлите сообщение из канала или введите корректный @username.")
        return

    try:
        bot_member = await message.bot.get_chat_member(chat_id=chat_id, user_id=message.bot.id)
        chat_info = await message.bot.get_chat(chat_id)

        # Проверка прав администратора
        if bot_member.status not in ["administrator", "creator"]:
            await message.answer("❌ Бот не является администратором в этом канале! Добавьте бота и повторите.")
            return

        if not getattr(bot_member, "can_post_messages", True) or not getattr(bot_member, "can_edit_messages", True):
            await message.answer("⚠️ У бота недостаточно прав! Убедитесь, что включены права на <b>публикацию</b> и <b>редактирование</b> сообщений.", parse_mode="HTML")
            return

        await db.add_channel(
            channel_id=chat_info.id,
            user_id=message.from_user.id,
            title=chat_info.title,
            username=chat_info.username
        )
        await state.clear()
        await message.answer(f"✅ Канал <b>{chat_info.title}</b> успешно привязан!", parse_mode="HTML")

    except Exception as e:
        await message.answer(f"❌ Ошибка подключения: {e}\nУбедитесь, что бот добавлен в канал.")

@channels_router.callback_query(F.data.startswith("del_channel_"))
async def delete_channel_cb(callback: types.CallbackQuery):
    channel_id = int(callback.data.split("_")[2])
    await db.delete_channel(channel_id, callback.from_user.id)
    await callback.answer("Канал отвязан!", show_alert=True)
    await callback.message.delete()