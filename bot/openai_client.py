import logging

from openai import AsyncOpenAI

from bot.config import OPENAI_API_KEY
from bot.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


async def get_ai_response(message: str) -> str:
    if not client:
        logger.error("OpenAI API key is not configured.")
        return "Произошла ошибка при обращении к AI. Попробуйте позже."

    try:
        response = await client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            max_tokens=520,
        )
        content = response.choices[0].message.content
        return content.strip() if content else "Не удалось получить ответ от AI."
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.exception("OpenAI request failed: %s", exc)
        return "Произошла ошибка при обращении к AI. Попробуйте позже."
