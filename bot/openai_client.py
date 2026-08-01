import logging

from openai import AsyncOpenAI

from bot.config import OPENAI_API_KEY
from bot.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
_RAW_LOG_LIMIT = 5
_raw_logged = 0


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

    # Preferred SDK helper: output_text()
    if hasattr(response, "output_text"):
        try:
            text = response.output_text()
            if text:
                return text
        except Exception:
            pass

    # Normalize to dict for robust parsing
    data = None
    if isinstance(response, dict):
        data = response
    elif hasattr(response, "to_dict"):
        try:
            data = response.to_dict()
        except Exception:
            data = None

    if isinstance(data, dict):
        # Common Responses API structure: 'output' is a list of items
        # Each item may contain 'content' which is a list of parts, including 'output_text'
        out = data.get("output") or []
        texts: list[str] = []
        for item in out:
            if not isinstance(item, dict):
                continue
            content_list = item.get("content") or []
            for part in content_list:
                if not isinstance(part, dict):
                    continue
                # Prefer explicit output_text parts
                if part.get("type") == "output_text" and part.get("text"):
                    texts.append(part.get("text"))
                # Fallback to generic text field
                elif part.get("text"):
                    texts.append(part.get("text"))

        if texts:
            return "\n\n".join(texts)

        # Older chat.completions-like shape fallback
        content = _get_dict_value(data, "choices", 0, "message", "content")
        if content:
            return content

    # Final fallback: try attribute-based choices/message parsing
    try:
        if hasattr(response, "choices"):
            choices = getattr(response, "choices")
            if choices:
                choice = choices[0]
                message = None
                if isinstance(choice, dict):
                    message = choice.get("message")
                else:
                    message = getattr(choice, "message", None)

                if message is not None:
                    if isinstance(message, dict):
                        return message.get("content") or message.get("text")
                    else:
                        return getattr(message, "content", None)
    except Exception:
        pass

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

        # If response incomplete due to token limits, attempt one retry with higher limit
        data = None
        try:
            data = response.to_dict() if hasattr(response, "to_dict") else (response if isinstance(response, dict) else None)
        except Exception:
            data = None

        incomplete = False
        prev_id = None
        if isinstance(data, dict):
            prev_id = data.get("id")
            incomplete = bool(data.get("incomplete_details")) or data.get("status") == "incomplete"

        if incomplete and client:
            try:
                retry_resp = await client.responses.create(
                    model="gpt-5-mini",
                    input=message,
                    instructions=SYSTEM_PROMPT,
                    max_output_tokens=2048,
                    previous_response_id=prev_id,
                )
                content = _extract_response_content(retry_resp)
                if content:
                    return content.strip()
                data = retry_resp.to_dict() if hasattr(retry_resp, "to_dict") else None
            except Exception:
                pass

        # Log raw response sparingly for debugging
        global _raw_logged
        try:
            if _raw_logged < _RAW_LOG_LIMIT:
                raw_response = getattr(response, "to_dict", lambda: repr(response))()
                logger.warning("OpenAI response missing content, falling back to raw response: %s", raw_response)
                _raw_logged += 1
        except Exception:
            logger.warning("OpenAI response missing content (failed to log raw response)")

        return "Не удалось получить ответ от AI."
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.exception("OpenAI request failed: %s", exc)
        return "Произошла ошибка при обращении к AI. Попробуйте позже."
