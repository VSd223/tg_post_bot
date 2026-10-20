from aiogram import Router, types
from aiogram.filters import CommandStart
from keyboards import get_main_menu
from database import db

start_router = Router()

@start_router.message(CommandStart())
async def cmd_start(message: types.Message):
    await db.add_user(message.from_user.id, message.from_user.username)
    welcome_text = (
        f"👋 Здравствуйте, <b>{message.from_user.first_name}</b>!\n\n"
        "Бот поддерживает:\n"
        "• <b>Кастомный текст Telegram</b>: скрытый текст (спойлеры), цитаты, кастомные эмодзи.\n"
        "• <b>4 типа кнопок</b>: Ссылки, Web App, Поделиться (Share) и Всплывающие окна (Alert).\n"
        "• Редактирование старых постов прямо в каналах.\n\n"
        "Добавьте бота в канал как администратора с правами публикации и подключите канал в меню."
    )
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=get_main_menu())

@start_router.message(lambda msg: msg.text == "ℹ️ Помощь по кнопкам и разметке")
async def show_help(message: types.Message):
    help_text = (
        "<b>📖 Поддерживаемые типы кнопок:</b>\n\n"
        "1. <b>Обычная ссылка:</b>\n"
        "<code>Сайт - https://example.com</code>\n\n"
        "2. <b>Web App (Приложение):</b>\n"
        "<code>Магазин - webapp:https://my-app.com</code>\n\n"
        "3. <b>Поделиться в чатах:</b>\n"
        "<code>Репост - share:Текст сообщения для пересылки</code>\n\n"
        "4. <b>Всплывающее окно (Alert):</b>\n"
        "<code>Правила - alert:Здесь любой текст оповещения!</code>\n\n"
        "<b>Расположение:</b>\n"
        "• Символ <code>|</code> ставит кнопки в один ряд.\n"
        "• Перенос строки создает новую строку кнопок.\n\n"
        "<b>Кастомный текст Telegram:</b>\n"
        "Вы можете форматировать текст прямо в клиенте Telegram (выделите текст -> выберите «Скрытый», «Цитата», добавьте премиум-эмодзи) — бот сохранит всё в первозданном виде."
    )
    await message.answer(help_text, parse_mode="HTML")