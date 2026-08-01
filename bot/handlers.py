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


def split_text(text: str, limit: int = 4000) -> list[str]:
    """Split text into chunks for Telegram (max 4096 chars per message).
    
    Algorithm per specification:
    1. Try to split by double newline (\\n\\n) - paragraph breaks
    2. Try to split by newline (\\n) - line breaks
    3. Try to split by sentence end (.!?) - sentence boundaries
    4. Split by space - word boundaries
    5. Force split at limit if no boundary found
    
    Uses limit=4000 to stay safely below Telegram's 4096 char limit.
    """
    if not text or len(text) <= limit:
        return [text] if text else []

    chunks = []
    start = 0

    while start < len(text):
        # Calculate end position
        end = min(start + limit, len(text))

        # If we're at the end of text, take rest
        if end >= len(text):
            remaining = text[start:].strip()
            if remaining:
                chunks.append(remaining)
            break

        # Find best split point in this section
        split_pos = -1

        # 1. Prefer double newline (paragraph)
        double_nl_pos = text.rfind("\n\n", start, end)
        if double_nl_pos > start:
            split_pos = double_nl_pos + 2
        
        # 2. Then single newline
        elif split_pos == -1:
            single_nl_pos = text.rfind("\n", start, end)
            if single_nl_pos > start:
                split_pos = single_nl_pos + 1

        # 3. Then sentence ending
        if split_pos == -1:
            for punct in [".", "!", "?"]:
                punct_pos = text.rfind(punct, start, end)
                if punct_pos > start:
                    split_pos = punct_pos + 1
                    break

        # 4. Finally, split by space
        if split_pos == -1:
            space_pos = text.rfind(" ", start, end)
            if space_pos > start:
                split_pos = space_pos + 1

        # If no good boundary, force split at limit
        if split_pos == -1:
            split_pos = end

        # Extract and clean chunk
        chunk = text[start:split_pos].strip()
        if chunk:
            chunks.append(chunk)

        start = split_pos

    return chunks


@router.message(F.text)
async def handle_text(message: Message) -> None:
    """Handle text messages: get AI response and send it (with chunking if needed)."""
    
    # Send initial typing indicator
    try:
        await message.bot.send_chat_action(
            chat_id=message.chat.id,
            action="typing"
        )
    except Exception:
        logger.debug("Initial typing action failed", exc_info=True)

    # Keep sending typing indicator while processing
    stop_event = asyncio.Event()
    typing_task = asyncio.create_task(
        _keep_typing(message.bot, message.chat.id, stop_event)
    )

    try:
        # Get AI response
        response_text = await get_ai_response(message.text or "")

        # Handle empty response
        if not response_text:
            await message.answer(
                "Произошла ошибка при обращении к AI. Попробуйте позже.",
                reply_to_message_id=message.message_id,
            )
            return

        # Split response into chunks
        chunks = split_text(response_text)
        if not chunks:
            await message.answer(
                "Произошла ошибка при обращении к AI. Попробуйте позже.",
                reply_to_message_id=message.message_id,
            )
            return

        # Send chunks with numbering
        total_chunks = len(chunks)
        for chunk_index, chunk_text in enumerate(chunks, 1):
            # Add header for multipart responses
            if total_chunks > 1:
                if chunk_index == 1:
                    header = f"📄 Часть {chunk_index}/{total_chunks}\n\n"
                else:
                    header = f"📄 Часть {chunk_index}/{total_chunks}\n\n"
                chunk_text = header + chunk_text

            # Send chunk
            if chunk_index == 1:
                # First chunk - reply to original message
                await message.answer(
                    chunk_text,
                    reply_to_message_id=message.message_id
                )
            else:
                # Subsequent chunks - standalone messages
                await message.answer(chunk_text)

                # Add delay between chunks to avoid spam detection
                if chunk_index < total_chunks:
                    await asyncio.sleep(0.5)

        # Log result
        if total_chunks > 1:
            logger.info(
                "Response split: %d chars into %d parts",
                len(response_text),
                total_chunks,
            )

    except Exception as exc:
        logger.exception("Message handling error: %s", exc)
        await message.answer(
            "Произошла ошибка при обращении к AI. Попробуйте позже.",
            reply_to_message_id=message.message_id,
        )

    finally:
        # Stop typing indicator
        stop_event.set()
        await typing_task


def register_handlers(dp) -> None:
    dp.include_router(router)
