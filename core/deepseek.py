import asyncio
import logging
from g4f.client import Client

logger = logging.getLogger(__name__)

# Используем синхронный клиент, запускаем в отдельном потоке

async def get_deepseek_response(system_prompt: str, user_prompt: str) -> str:
    def _call_sync():
        try:
            client = Client()
            response = client.chat.completions.create(
                model="deepseek-v3",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            if not response:
                logger.warning("deepseek response is empty")
                return None
            content = response.choices[0].message.content
            logger.info("deepseek response received: %s", content[:100] if content else "None")
            return content
        except Exception as e:
            logger.error("deepseek error: %s", e)
            return None
    
    # Запускаем синхронный код в отдельном потоке
    return await asyncio.to_thread(_call_sync)