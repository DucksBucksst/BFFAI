import asyncio
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


async def _keep_typing(bot, chat_id: int, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception:
            pass
        await asyncio.sleep(4)


@router.message(F.text)
async def handle_text(message: Message) -> None:
    stop_event = asyncio.Event()
    typing_task = asyncio.create_task(
        _keep_typing(message.bot, message.chat.id, stop_event)
    )

    try:
        response = await get_ai_response(message.text or "")
        await message.answer(response, reply_to_message_id=message.message_id)
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.exception("Telegram message handling failed: %s", exc)
        await message.answer(
            "Произошла ошибка при обращении к AI. Попробуйте позже.",
            reply_to_message_id=message.message_id,
        )
    finally:
        stop_event.set()
        await typing_task


def register_handlers(dp) -> None:
    dp.include_router(router)
