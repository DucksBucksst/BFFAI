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


def _collect_text_values(obj) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        texts: list[str] = []
        for key, value in obj.items():
            if key == "text" and isinstance(value, str):
                texts.append(value)
            else:
                texts.extend(_collect_text_values(value))
        return texts
    if isinstance(obj, list):
        texts: list[str] = []
        for item in obj:
            texts.extend(_collect_text_values(item))
        return texts
    return []


def _extract_response_content(response) -> str | None:
    if response is None:
        logger.warning("Response is None")
        return None

    # Preferred SDK helper: output_text()
    if hasattr(response, "output_text"):
        try:
            text = response.output_text()
            if text:
                logger.debug("Extracted via output_text()")
                return text
        except Exception as e:
            logger.debug("output_text() failed: %s", e)

    # Normalize to dict for robust parsing
    data = None
    if isinstance(response, dict):
        data = response
    elif hasattr(response, "to_dict"):
        try:
            data = response.to_dict()
        except Exception as e:
            logger.debug("to_dict() failed: %s", e)
            data = None

    if isinstance(data, dict):
        # Common Responses API structure: 'output' is a list of items
        out = data.get("output") or []
        logger.debug("Response data keys: %s", list(data.keys()))
        logger.debug("Output list length: %d", len(out))

        texts = _collect_text_values(out)
        if texts:
            logger.debug("Extracted text values from output list")
            return "\n\n".join(texts)

        # Some Responses items may include top-level output_text
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            logger.debug("Extracted from output_text field")
            return output_text.strip()

        # Older chat.completions-like shape fallback
        content = _get_dict_value(data, "choices", 0, "message", "content")
        if content:
            logger.debug("Extracted from choices[] fallback")
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
                        content = message.get("content") or message.get("text")
                        if content:
                            logger.debug("Extracted from choices attribute fallback")
                            return content
                    else:
                        content = getattr(message, "content", None)
                        if content:
                            logger.debug("Extracted from message attribute")
                            return content
    except Exception as e:
        logger.debug("Attribute parsing failed: %s", e)

    logger.warning("Could not extract content from response: %s", str(data)[:400] if data else "no data")
    return None


async def get_ai_response(message: str) -> str:
    """Get AI response from OpenAI Responses API.
    
    Uses max_output_tokens=8192 to ensure long responses aren't truncated.
    Returns raw text response to be chunked by handler.
    """
    if not client:
        logger.error("OpenAI API key is not configured.")
        return ""

    try:
        logger.debug("Sending request to OpenAI with message: %s...", message[:50])
        
        response = await client.responses.create(
            model="gpt-5-mini",
            input=message,
            instructions=SYSTEM_PROMPT,
            max_output_tokens=8192,
            reasoning={"effort": "medium"},
        )

        logger.debug("OpenAI response received, extracting content...")
        content = _extract_response_content(response)
        
        if content and content.strip():
            logger.info("Successfully extracted %d characters from response", len(content))
            return content.strip()

        # No content extracted - log warning and return empty string
        logger.warning("OpenAI response returned but no text content extracted")
        return ""
        
    except Exception as exc:
        logger.exception("OpenAI request failed: %s", exc)
        return ""
