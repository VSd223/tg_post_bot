import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from database import db
from handlers.start import start_router
from handlers.channels import channels_router
from handlers.create_post import post_router
from handlers.edit_post import edit_router
from handlers.callbacks import callbacks_router
from handlers.scheduled import scheduled_router
from scheduler import start_scheduler_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def main():
    if not config.BOT_TOKEN or config.BOT_TOKEN == "ВАШ_ТОКЕН_БОТА_ЗДЕСЬ":
        logger.error("ОШИБКА: Задайте токен бота в файле config.py или в переменной BOT_TOKEN!")
        return

    await db.init()
    logger.info("База данных готова.")

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация всех роутеров
    dp.include_router(start_router)
    dp.include_router(channels_router)
    dp.include_router(post_router)
    dp.include_router(edit_router)
    dp.include_router(callbacks_router)
    dp.include_router(scheduled_router)

    # Запуск фонового планировщика постов и автоудаления
    asyncio.create_task(start_scheduler_loop(bot))

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот с планировщиком по МСК успешно запущен!")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")