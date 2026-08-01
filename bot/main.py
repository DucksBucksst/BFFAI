import asyncio
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aiogram import Bot, Dispatcher

from bot.config import BOT_TOKEN, get_required_env
from bot.handlers import register_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def main() -> None:
    token = BOT_TOKEN or get_required_env("BOT_TOKEN")
    bot = Bot(token=token)
    dp = Dispatcher()
    register_handlers(dp)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
