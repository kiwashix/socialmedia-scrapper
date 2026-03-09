import aiohttp
import logging
from core.config import SCITELY_API_KEY

logger = logging.getLogger(__name__)

URL = "https://api.scitely.com/v1/chat/completions"
MODEL = "deepseek-v3"
HEADERS = {
    "Authorization": f"Bearer {SCITELY_API_KEY}",
    "Content-Type": "application/json",
}


async def get_scitely_response(system_prompt: str, user_prompt: str) -> str | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                URL,
                headers=HEADERS,
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 750,
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 401:
                    logger.error("SCITELY API: Invalid API key")
                    return None
                if resp.status == 403:
                    logger.error("SCITELY API: Forbidden")
                    return None
                if resp.status == 429:
                    logger.error("SCITELY API: HTTP 429 (rate limit)")
                    return None
                if resp.status != 200:
                    logger.error("SCITELY API: HTTP %d", resp.status)
                    return None

                data_resp = await resp.json()

        # Scitely иногда возвращает ошибку в теле при статусе 200
        if "error" in data_resp:
            logger.error("SCITELY API error in body: %s", data_resp["error"])
            return None

        choices = data_resp.get("choices")
        if not choices:
            # Логируем реальный ответ для диагностики
            logger.error("SCITELY: unexpected response format: %s", str(data_resp)[:300])
            return None

        raw = choices[0].get("message", {}).get("content", "").strip()
        if not raw:
            logger.error("SCITELY: empty content in response")
            return None

        logger.info("Scitely response received: %s", raw[:100])
        return raw

    except aiohttp.ClientError as e:
        logger.error("SCITELY network error: %s", e)
        return None
    except Exception as e:
        logger.error("SCITELY error: %s", e)
        return None
