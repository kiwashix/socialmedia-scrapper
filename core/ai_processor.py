from __future__ import annotations
import json
import logging
from dataclasses import dataclass
from typing import Optional

from core.config import SUMMARY_LANGUAGE
from parsers.base import NewsItem
from core.deepseek import get_deepseek_response
from core.groq import get_groq_response
from core.scitely import get_scitely_response

logger = logging.getLogger(__name__)


@dataclass
class ProcessedItem:
    original: NewsItem
    is_relevant: bool
    category: str
    summary: str
    emoji: str
    formatted_message: str


SYSTEM_PROMPT = f"""You are a news curator for a Telegram channel about the video games.
Your job is to process raw news items and decide whether they are worth sending to subscribers.

Your tasks for each item:
1. RELEVANCE CHECK: Is this genuinely about VALORANT/MARATHON (by Bungie Studio)/CS2/PUBG?
   Return is_relevant: true/false.

2. CATEGORY: Classify as one of:
   "Official Update" – directly from official channels
   "Media" – trailers, screenshots, videos, gameplay footage
   "Community" – notable Reddit/fan posts, fan art, discussions
   "News" – third-party journalism / reviews / previews
   "Rumour" – unconfirmed leaks or speculation

3. SUMMARY: Write a crisp 2-3 sentence summary in {SUMMARY_LANGUAGE}. Be concise, factual,
   and highlight what's new or interesting. Do NOT start with "This article...".

4. EMOJI: Choose one fitting emoji for the category.

Respond ONLY in this exact JSON format (no markdown, no extra text):
{{
  "is_relevant": true,
  "category": "Official Update",
  "emoji": "📢",
  "summary": "Your 2-3 sentence summary here."
}}"""

AI_ENDPOINTS = [get_deepseek_response, get_groq_response, get_scitely_response]

async def process_item(item: NewsItem) -> Optional[ProcessedItem]:
    """Run a NewsItem through Groq LLM and return a ProcessedItem."""
    prompt = f"""Source: {item.source}
Title: {item.title}
URL: {item.url}
Published: {item.published}
Author: {item.author}

Content:
{item.body[:6000]}"""

    try:
        raw = None
        for endpoint in AI_ENDPOINTS:
            try:
                resp = await endpoint(SYSTEM_PROMPT, prompt)
                if resp is not None:
                    raw = resp
                    logger.info(f"Endpoint {endpoint.__name__} succeeded")
                    break
                else:
                    logger.warning(f"Endpoint {endpoint.__name__} returned None")
            except Exception as e:
                logger.warning(f"Endpoint {endpoint.__name__} raised exception: {e}")
                continue
        
        if raw is None:
            logger.error("All AI endpoints failed - using fallback")
            return _fallback_process(item)
                
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)

        is_relevant = bool(data.get("is_relevant", False))
        category = data.get("category", "News")
        emoji = data.get("emoji", "📰")
        summary = data.get("summary", item.title)

        formatted = _format_telegram_message(item, category, emoji, summary)
        return ProcessedItem(
            original=item,
            is_relevant=is_relevant,
            category=category,
            summary=summary,
            emoji=emoji,
            formatted_message=formatted,
        )
    except Exception as exc:
        logger.error("AI processing failed for '%s': %s", item.title, exc, exc_info=True)
        return _fallback_process(item)


def _format_telegram_message(
    item: NewsItem, category: str, emoji: str, summary: str
) -> str:
    parts = []
    parts.append(f"{emoji} <b>{_esc(item.title)}</b>")
    parts.append(f"<i>📌 {_esc(category)} | 🔗 {_esc(item.source)}</i>")
    parts.append("")
    parts.append(_esc(summary))
    parts.append("")
    if item.author:
        parts.append(f"👤 <i>{_esc(item.author)}</i>")
    if item.score:
        parts.append(f"⬆️ Score: {item.score}")
    if item.published:
        parts.append(f"🕒 {_esc(item.published[:19].replace('T', ' '))} UTC")
    if item.tags:
        parts.append(f"🏷 {' '.join(_esc(t) for t in item.tags if t)}")
    parts.append("")
    parts.append(f'<a href="{item.url}">Read full article →</a>')
    if item.media_urls:
        parts.append("")
        parts.append("🖼 <b>Media:</b>")
        for i, murl in enumerate(item.media_urls[:5], 1):
            parts.append(f"  {i}. <a href=\"{murl}\">{_media_label(murl)}</a>")
    return "\n".join(parts)


def _fallback_process(item: NewsItem) -> ProcessedItem:
    """Fallback when AI is unavailable. Marks as processed but NOT relevant —
    prevents spam when the AI API is broken."""
    msg = (
        f"📰 <b>{_esc(item.title)}</b>\n"
        f"<i>{_esc(item.source)}</i>\n\n"
        f'<a href="{item.url}">Read more →</a>'
    )
    return ProcessedItem(
        original=item,
        is_relevant=False,  # не отправляем если AI недоступен
        category="News",
        summary=item.title,
        emoji="📰",
        formatted_message=msg,
    )


def _esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _media_label(url: str) -> str:
    if any(ext in url for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp")):
        return "Image"
    if any(ext in url for ext in (".mp4", ".webm")):
        return "Video"
    if "youtube.com" in url or "youtu.be" in url:
        return "YouTube Video"
    return "Media"
