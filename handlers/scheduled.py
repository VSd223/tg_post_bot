from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import db

scheduled_router = Router()

@scheduled_router.message(F.text == "⏰ Запланированные посты")
async def show_scheduled_posts(message: types.Message):
    posts = await db.get_user_scheduled_posts(message.from_user.id)
    if not posts:
        await message.answer("📭 У вас нет постов, ожидающих публикации.")
        return

    text = "<b>⏰ Ваши запланированные посты:</b>\n\n"
    builder = InlineKeyboardBuilder()

    for p in posts:
        preview = (p['raw_text'][:20] + "...") if p['raw_text'] else f"Медиа ({p['content_type']})"
        text += (
            f"• <b>Пост #{p['id']}</b> в канал <b>{p['channel_title']}</b>\n"
            f"  📅 Публикация: <code>{p['publish_at']} (МСК)</code>\n"
            f"  💬 Текст: {preview}\n\n"
        )
        builder.row(types.InlineKeyboardButton(text=f"❌ Отменить пост #{p['id']}", callback_data=f"cancel_sch_{p['id']}"))

    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())

@scheduled_router.callback_query(F.data.startswith("cancel_sch_"))
async def cancel_scheduled_cb(callback: types.CallbackQuery):
    post_id = int(callback.data.split("_")[2])
    success = await db.cancel_scheduled_post(post_id, callback.from_user.id)
    if success:
        await callback.answer(f"Пост #{post_id} удален из очереди!", show_alert=True)
        await callback.message.delete()
    else:
        await callback.answer("Пост уже был опубликован или отменен.", show_alert=True)