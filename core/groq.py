import aiohttp
import logging
from core.config import GROQ_API_KEY

logger = logging.getLogger(__name__)

URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json",
}

async def get_groq_response(system_prompt: str, user_prompt: str) -> str:
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
                    logger.error("GROQ API: Invalid API key. Check GROQ_API_KEY in .env")
                    return None
                if resp.status == 403:
                    logger.error("GROQ API: Forbidden - API key may be invalid or expired")
                    return None
                if resp.status != 200:
                    logger.error("GROQ API: HTTP %d", resp.status)
                    return None
                    
                data_resp = await resp.json()

        raw = data_resp["choices"][0]["message"]["content"].strip()
        
        if raw is not None:
             logger.info("Groq response received: %s", raw[:100])
             return raw
        return None
    except aiohttp.ClientError as e:
        logger.error("GROQ network error: %s", e)
        return None
    except Exception as e:
        logger.error("GROQ error: %s", e)
        return None