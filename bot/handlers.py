import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.openai_client import get_ai_response

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer("Привет! Я AI-ассистент.\nЗадавай мне любые вопросы.")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer("Просто отправь сообщение, и я отвечу с помощью AI.")


@router.message(F.text)
async def handle_text(message: Message) -> None:
    try:
        response = await get_ai_response(message.text or "")
        await message.answer(response)
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.exception("Telegram message handling failed: %s", exc)
        await message.answer("Произошла ошибка при обращении к AI. Попробуйте позже.")


def register_handlers(dp) -> None:
    dp.include_router(router)
