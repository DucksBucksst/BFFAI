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
            logger.debug("Failed to send typing action", exc_info=True)
        await asyncio.sleep(2)


def split_text(text: str, limit: int = 3800) -> list[str]:
    """Split text into chunks with smart boundary detection.
    
    Prioritizes:
    1. Double newline (\\n\\n) - paragraph breaks
    2. Single newline (\\n) - line breaks  
    3. Sentence end (.!?) - sentence boundaries
    4. Space - word boundaries
    """
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    start = 0
    
    while start < len(text):
        end = min(start + limit, len(text))
        
        # Already at end of text
        if end >= len(text):
            chunks.append(text[start:].strip())
            break
        
        # Try to find split point in order of preference
        split_pos = -1
        
        # 1. Prefer double newline (\n\n)
        double_newline = text.rfind("\n\n", start, end)
        if double_newline > start:
            split_pos = double_newline + 2
        
        # 2. Then single newline (\n)
        if split_pos == -1:
            single_newline = text.rfind("\n", start, end)
            if single_newline > start:
                split_pos = single_newline + 1
        
        # 3. Then sentence end (.!?)
        if split_pos == -1:
            for punct in (".", "!", "?"):
                punct_pos = text.rfind(punct, start, end)
                if punct_pos > start:
                    split_pos = punct_pos + 1
                    break
        
        # 4. Finally, split by space
        if split_pos == -1:
            space_pos = text.rfind(" ", start, end)
            if space_pos > start:
                split_pos = space_pos + 1
        
        # If no boundary found, cut at limit
        if split_pos == -1:
            split_pos = end
        
        chunk = text[start:split_pos].strip()
        if chunk:
            chunks.append(chunk)
        start = split_pos
    
    return chunks


@router.message(F.text)
async def handle_text(message: Message) -> None:
    try:
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    except Exception:
        logger.debug("Initial typing action failed", exc_info=True)

    stop_event = asyncio.Event()
    typing_task = asyncio.create_task(
        _keep_typing(message.bot, message.chat.id, stop_event)
    )

    try:
        response = await get_ai_response(message.text or "")
        chunks = split_text(response)
        if not chunks:
            await message.answer(
                "Не удалось получить ответ от AI.",
                reply_to_message_id=message.message_id,
            )
        else:
            total = len(chunks)
            for index, chunk in enumerate(chunks):
                # Add part numbering if multiple chunks
                if total > 1:
                    header = f"\n📄 Часть {index + 1}/{total}\n" if index > 0 else f"📄 Часть {index + 1}/{total}\n"
                    chunk = header + chunk
                
                if index == 0:
                    await message.answer(chunk, reply_to_message_id=message.message_id)
                else:
                    await message.answer(chunk)
                    # Add delay between messages to avoid spam detection
                    if index < total - 1:
                        await asyncio.sleep(0.5)
            
            # Log chunked response
            if total > 1:
                logger.info(
                    "Response chunked: %d chars -> %d messages",
                    len(response),
                    total,
                )
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
