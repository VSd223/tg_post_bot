from aiogram import Router, types, F

callbacks_router = Router()

@callbacks_router.callback_query(F.data.startswith("al:"))
async def handle_alert_buttons(callback: types.CallbackQuery):
    alert_text = callback.data.replace("al:", "", 1)
    # Показывает нативное всплывающее диалоговое окно в Telegram
    await callback.answer(text=alert_text, show_alert=True)