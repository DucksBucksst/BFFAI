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
    """Get AI response from OpenAI Responses API.
    
    Uses max_output_tokens=4096 to ensure long responses aren't truncated.
    Returns raw text response to be chunked by handler.
    """
    if not client:
        logger.error("OpenAI API key is not configured.")
        return ""

    try:
        response = await client.responses.create(
            model="gpt-5-mini",
            input=message,
            instructions=SYSTEM_PROMPT,
            max_output_tokens=4096,
        )

        content = _extract_response_content(response)
        if content and content.strip():
            return content.strip()

        # No content extracted - log warning but don't fail
        logger.warning("OpenAI response empty or missing content")
        return ""
        
    except Exception as exc:
        logger.exception("OpenAI request failed: %s", exc)
        return ""
