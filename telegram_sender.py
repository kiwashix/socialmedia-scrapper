"""
telegram_sender.py – Sends formatted messages (and optionally media) to a
Telegram chat/channel using python-telegram-bot.
"""
from __future__ import annotations
import asyncio
import logging
from typing import List

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from core.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from core.ai_processor import ProcessedItem

logger = logging.getLogger(__name__)

# Telegram message length limit
MAX_MSG_LEN = 4096


class TelegramSender:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.chat_id = TELEGRAM_CHAT_ID

    async def send_item(self, processed: ProcessedItem) -> bool:
        """Send a single processed news item to Telegram. Returns True on success."""
        item = processed.original
        message = processed.formatted_message

        # Truncate if needed
        if len(message) > MAX_MSG_LEN:
            message = message[: MAX_MSG_LEN - 30] + "\n… <i>(truncated)</i>"

        # Try to send a photo with caption first (looks nicer in Telegram)
        if item.media_urls:
            first_media = item.media_urls[0]
            if _is_image(first_media):
                sent = await self._try_send_photo(first_media, message)
                if sent:
                    return True

        # Fall back to plain text message
        return await self._send_text(message)

    async def _try_send_photo(self, photo_url: str, caption: str) -> bool:
        """Attempt to send a photo with caption. Caption limited to 1024 chars."""
        try:
            cap = caption[:1024]
            await self.bot.send_photo(
                chat_id=self.chat_id,
                photo=photo_url,
                caption=cap,
                parse_mode=ParseMode.HTML,
            )
            return True
        except TelegramError as exc:
            logger.debug("send_photo failed (%s), falling back to text", exc)
            return False

    async def _send_text(self, message: str) -> bool:
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )
            return True
        except TelegramError as exc:
            logger.error("send_message failed: %s", exc)
            return False

    async def send_startup_message(self) -> None:
        msg = (
            "🤖 <b>Бот сетки запущен!</b>\n\n"
            "🔎 Начинаю мониторить новости по:\n"
            "• CS2\n"
            "• MARATHON\n"
            "• PUBG\n"
            "• VALORANT\n"
            "🤔 Буду мониторить:\n"
            "• Reddit\n"
            "• RSS ленты\n"
            "• Steam страницы\n"
            "• X (Twitter)\n"
            "• YouTube\n\n"
            "🔥 Как только появятся новости - дам тебе знать!"
        )
        await self._send_text(msg)

    async def send_error_report(self, error: str) -> None:
        msg = f"⚠️ <b>Bot Error</b>\n\n<code>{error[:500]}</code>"
        await self._send_text(msg)

    async def send_batch(self, items: List[ProcessedItem], delay: float = 1.5) -> int:
        """Send multiple items with a delay between each to avoid rate limiting."""
        sent_count = 0
        for processed in items:
            success = await self.send_item(processed)
            if success:
                sent_count += 1
            await asyncio.sleep(delay)
        return sent_count


def _is_image(url: str) -> bool:
    url_lower = url.lower().split("?")[0]
    return any(url_lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"))
