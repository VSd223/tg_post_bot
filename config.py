import os
from dataclasses import dataclass

@dataclass
class Config:
    # Бот берет токен из системы/файла .env, в коде токен не хранится!
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    DB_PATH: str = "bot_database.sqlite3"

config = Config()