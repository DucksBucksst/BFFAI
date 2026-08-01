import logging

from openai import AsyncOpenAI

from bot.config import OPENAI_API_KEY
from bot.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def _get_dict_value(obj, *keys):
    if not isinstance(obj, dict):
        return None
    current = obj
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def _extract_response_content(response) -> str | None:
    if response is None:
        return None

    if hasattr(response, "output_text"):
        try:
            text = response.output_text()
            if text:
                return text
        except Exception:
            pass

    if isinstance(response, dict):
        content = _get_dict_value(response, "output_text")
        if content:
            return content

    if hasattr(response, "choices"):
        try:
            choices = response.choices
            if choices:
                choice = choices[0]
                message = None
                if isinstance(choice, dict):
                    message = choice.get("message")
                else:
                    message = getattr(choice, "message", None)

                if message is None and hasattr(choice, "to_dict"):
                    try:
                        data = choice.to_dict()
                        message = data.get("message")
                    except Exception:
                        message = None

                if message is not None:
                    if isinstance(message, dict):
                        content = message.get("content") or message.get("text")
                    else:
                        content = getattr(message, "content", None)
                        if not content and hasattr(message, "parsed"):
                            parsed = getattr(message, "parsed")
                            content = str(parsed) if parsed is not None else None

                    if content:
                        return content
        except Exception:
            pass

    if isinstance(response, dict):
        content = _get_dict_value(response, "choices", 0, "message", "content")
        if content:
            return content
        content = _get_dict_value(response, "choices", 0, "message", "text")
        if content:
            return content

    return None


async def get_ai_response(message: str) -> str:
    if not client:
        logger.error("OpenAI API key is not configured.")
        return "Произошла ошибка при обращении к AI. Попробуйте позже."

    try:
        response = await client.responses.create(
            model="gpt-5-mini",
            input=message,
            instructions=SYSTEM_PROMPT,
            max_output_tokens=1200,
        )

        content = _extract_response_content(response)
        if content:
            return content.strip()

        raw_response = getattr(response, "to_dict", lambda: repr(response))()
        logger.warning(
            "OpenAI response missing content, falling back to raw response: %s",
            raw_response,
        )
        return "Не удалось получить ответ от AI."
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.exception("OpenAI request failed: %s", exc)
        return "Произошла ошибка при обращении к AI. Попробуйте позже."
