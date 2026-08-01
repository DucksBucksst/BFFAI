import asyncio
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.openai_client import get_ai_response

logger = logging.getLogger(__name__)
router = Router()
chat_histories: dict[int, list[tuple[str, str]]] = {}


def build_user_prompt(message: Message) -> str:
    history = chat_histories.get(message.chat.id, [])[-6:]
    prompt_parts: list[str] = []

    if history:
        prompt_parts.append("Предыдущая беседа:")
        for role, text in history:
            prompt_parts.append(f"{role}: {text}")
        prompt_parts.append("---")

    if message.reply_to_message and message.reply_to_message.text:
        prompt_parts.append("Предыдущее сообщение, на которое ответили:")
        prompt_parts.append(message.reply_to_message.text)
        prompt_parts.append("---")

    prompt_parts.append("Текущий запрос пользователя:")
    prompt_parts.append(message.text or "")

    return "\n".join(prompt_parts)


def save_chat_history(chat_id: int, role: str, text: str) -> None:
    history = chat_histories.setdefault(chat_id, [])
    history.append((role, text))
    if len(history) > 12:
        del history[: len(history) - 12]


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
        prompt = build_user_prompt(message)
        logger.info("Processing message from user: %s...", (message.text or "")[:50])
        response_text = await get_ai_response(prompt)
        logger.info("Got response: %d chars", len(response_text) if response_text else 0)

        # Handle empty response
        if not response_text:
            logger.warning("Empty response from AI, sending error message")
            await message.answer(
                "Произошла ошибка при обращении к AI. Попробуйте позже.",
                reply_to_message_id=message.message_id,
            )
            return

        # Split response into chunks
        chunks = split_text(response_text)
        logger.info("Response split into %d chunks", len(chunks))
        
        if not chunks:
            logger.warning("No chunks generated, sending error message")
            await message.answer(
                "Произошла ошибка при обращении к AI. Попробуйте позже.",
                reply_to_message_id=message.message_id,
            )
            return

        # Save chat history before sending response
        save_chat_history(message.chat.id, "Пользователь", message.text or "")

        # Send chunks with numbering
        total_chunks = len(chunks)
        for chunk_index, chunk_text in enumerate(chunks, 1):
            # Add header for multipart responses
            if total_chunks > 1:
                header = f"📄 Часть {chunk_index}/{total_chunks}\n\n"
                chunk_text = header + chunk_text

            # ALL chunks reply to original message
            logger.debug("Sending chunk %d/%d", chunk_index, total_chunks)
            await message.answer(
                chunk_text,
                reply_to_message_id=message.message_id
            )

        # Save bot response to history
        save_chat_history(message.chat.id, "Ассистент", response_text)

        # Add delay between chunks to avoid spam detection
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
