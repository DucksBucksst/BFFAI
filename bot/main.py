import asyncio
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiohttp import web

from bot.config import BOT_TOKEN, get_required_env
from bot.handlers import register_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def handle_webhook(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    dispatcher = request.app["dispatcher"]
    payload = await request.json()
    update = Update(**payload)
    await dispatcher.feed_webhook_update(bot, update)
    return web.Response(text="OK")


async def main() -> None:
    token = BOT_TOKEN or get_required_env("BOT_TOKEN")
    webhook_url = os.getenv("WEBHOOK_URL", "").strip()
    use_webhook = bool(webhook_url)

    bot = Bot(token=token)
    dp = Dispatcher()
    register_handlers(dp)

    if use_webhook:
        app = web.Application()
        app["bot"] = bot
        app["dispatcher"] = dp
        app.router.add_post("/webhook", handle_webhook)

        await bot.set_webhook(f"{webhook_url}/webhook")

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
        await site.start()

        logging.info("Webhook server started on %s", os.getenv("PORT", "8000"))
        while True:
            await asyncio.sleep(3600)
    else:
        try:
            await dp.start_polling(bot)
        finally:
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
