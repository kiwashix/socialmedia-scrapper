"""
parsers/youtube.py – Watches the official Bungie YouTube channel for new
Marathon-related videos using the public Atom/RSS feed (no API key needed).
"""
from __future__ import annotations
import re
from typing import List

import aiohttp
import feedparser

from parsers.base import BaseParser, NewsItem

# Bungie's official YouTube channel ID
BUNGIE_CHANNEL_ID = "UCpXBGqwsBkpvcYjsJBQ7LEg"
YT_RSS_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={BUNGIE_CHANNEL_ID}"

# Keywords that suggest Marathon content
MARATHON_KEYWORDS = [
    "marathon", "runner", "tau ceti", "extraction shooter",
    "bungie new game", "marathon game",
]


class YouTubeParser(BaseParser):
    SOURCE_NAME = "YouTube – Bungie"
    SOURCE_KEY = "youtube"

    async def fetch(self) -> List[NewsItem]:
        items: List[NewsItem] = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    YT_RSS_URL,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        self.logger.warning("YouTube RSS returned %s", resp.status)
                        return items
                    content = await resp.text()

            feed = feedparser.parse(content)
            for entry in feed.entries:
                title = entry.get("title", "")
                # Filter to Marathon-relevant videos only
                if not _is_marathon_related(title):
                    continue

                video_id = entry.get("yt_videoid", "")
                if not video_id:
                    video_id = _extract_video_id(entry.get("link", ""))
                if not video_id:
                    continue

                url = f"https://www.youtube.com/watch?v={video_id}"
                thumbnail = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
                description = entry.get("summary", "")[:1000]
                published = entry.get("published", "")

                items.append(NewsItem(
                    source=self.SOURCE_NAME,
                    source_key=self.SOURCE_KEY,
                    item_id=video_id,
                    title=title,
                    url=url,
                    body=description,
                    published=published,
                    author="Bungie",
                    media_urls=[thumbnail, url],  # thumbnail + video link
                ))
        except Exception as exc:
            self.logger.error("YouTubeParser error: %s", exc, exc_info=True)
        return items


def _is_marathon_related(title: str) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in MARATHON_KEYWORDS)


def _extract_video_id(url: str) -> str:
    m = re.search(r"v=([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else ""
