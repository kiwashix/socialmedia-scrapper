"""
parsers/youtube.py – Watches YouTube channels for new
related videos using the public Atom/RSS feed (no API key needed).
"""
from __future__ import annotations
import re
from typing import List
import aiohttp
import feedparser
from parsers.base import BaseParser, NewsItem

TIMEOUT = aiohttp.ClientTimeout(total=30)
MAX_RETRIES = 3


class YouTubeParser(BaseParser):

    def __init__(self, source_config: dict):
        super().__init__()
        self.config = source_config
        self.SOURCE_NAME = source_config['id']
        self.SOURCE_KEY = f"{source_config['type']}:{source_config['id']}"
        self.YT_RSS_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={source_config['channel_id']}"
        self.CHANNEL = source_config['channel']

    async def fetch(self) -> List[NewsItem]:
        items: List[NewsItem] = []
        last_exc = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        self.YT_RSS_URL,
                        timeout=TIMEOUT,
                    ) as resp:
                        if resp.status != 200:
                            self.logger.warning(
                                "YouTube RSS returned %s (attempt %d/%d)",
                                resp.status, attempt, MAX_RETRIES,
                            )
                            return items
                        content = await resp.text()

                feed = feedparser.parse(content)
                for entry in feed.entries:
                    title = entry.get("title", "")
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
                        author=self.CHANNEL,
                        media_urls=[thumbnail, url],
                    ))
                return items  # успех

            except Exception as exc:
                last_exc = exc
                self.logger.warning(
                    "YouTubeParser attempt %d/%d failed: %s",
                    attempt, MAX_RETRIES, exc,
                )

        self.logger.error("YouTubeParser error after %d attempts: %s", MAX_RETRIES, last_exc)
        return items


def _extract_video_id(url: str) -> str:
    m = re.search(r"v=([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else ""
