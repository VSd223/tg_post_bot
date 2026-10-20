import asyncio
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import List
from aiogram import Bot
from aiogram.types import MessageEntity
from database import db
from keyboards import build_inline_markup

logger = logging.getLogger(__name__)

# Часовой пояс Москва: UTC+3
MSK_TZ = timezone(timedelta(hours=3))

def get_now_msk() -> datetime:
    return datetime.now(MSK_TZ)

def format_datetime_msk(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def deserialize_entities(entities_json: str) -> List[MessageEntity]:
    if not entities_json:
        return []
    try:
        data = json.loads(entities_json)
        return [MessageEntity(**item) for item in data]
    except Exception:
        return []

async def execute_scheduled_posts(bot: Bot):
    now_str = format_datetime_msk(get_now_msk())
    due_posts = await db.get_due_scheduled_posts(now_str)

    for post in due_posts:
        post_id = post["id"]
        channel_id = post["channel_id"]
        content_type = post["content_type"]
        raw_text = post["raw_text"] or ""
        file_id = post["file_id"]
        entities = deserialize_entities(post.get("entities_json", "[]"))
        buttons_data = json.loads(post.get("buttons_json", "[]")) if post.get("buttons_json") else []

        markup = build_inline_markup(buttons_data)

        try:
            if content_type == "text":
                msg = await bot.send_message(
                    chat_id=channel_id,
                    text=raw_text,
                    entities=entities,
                    reply_markup=markup
                )
            elif content_type == "photo":
                msg = await bot.send_photo(
                    chat_id=channel_id,
                    photo=file_id,
                    caption=raw_text,
                    caption_entities=entities,
                    reply_markup=markup
                )
            elif content_type == "video":
                msg = await bot.send_video(
                    chat_id=channel_id,
                    video=file_id,
                    caption=raw_text,
                    caption_entities=entities,
                    reply_markup=markup
                )
            elif content_type == "animation":
                msg = await bot.send_animation(
                    chat_id=channel_id,
                    animation=file_id,
                    caption=raw_text,
                    caption_entities=entities,
                    reply_markup=markup
                )

            await db.mark_post_published(post_id, msg.message_id)
            logger.info(f"Запланированный пост #{post_id} успешно опубликован в канал {channel_id}")

            try:
                await bot.send_message(
                    chat_id=post["user_id"],
                    text=f"✅ Ваш запланированный пост #{post_id} только что успешно опубликован в канале!"
                )
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Ошибка при публикации запланированного поста #{post_id}: {e}")

async def execute_auto_deletions(bot: Bot):
    now_str = format_datetime_msk(get_now_msk())
    due_deletes = await db.get_due_delete_posts(now_str)

    for post in due_deletes:
        post_id = post["id"]
        channel_id = post["channel_id"]
        message_id = post["message_id"]

        try:
            if message_id:
                await bot.delete_message(chat_id=channel_id, message_id=message_id)
            await db.mark_post_deleted(post_id)
            logger.info(f"Пост #{post_id} (msg: {message_id}) автоматически удален из канала {channel_id}")
        except Exception as e:
            logger.error(f"Не удалось удалить пост #{post_id} из канала: {e}")
            await db.mark_post_deleted(post_id)

async def start_scheduler_loop(bot: Bot):
    """Бесконечный фоновый воркер, проверяющий расписание каждые 15 секунд"""
    logger.info("Фоновый планировщик постов по МСК запущен.")
    while True:
        try:
            await execute_scheduled_posts(bot)
            await execute_auto_deletions(bot)
        except Exception as e:
            logger.error(f"Ошибка в цикле планировщика: {e}")
        await asyncio.sleep(15)