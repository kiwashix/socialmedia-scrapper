"""
parsers/gaming_news.py – Monitors major gaming news sites' RSS feeds for
articles mentioning Marathon. No API keys needed.

Sources:
  • IGN         – https://feeds.feedburner.com/ign/all
  • PCGamer     – https://www.pcgamer.com/rss/
  • GamesRadar  – https://www.gamesradar.com/rss/
  • Kotaku      – https://kotaku.com/rss
  • Eurogamer   – https://www.eurogamer.net/?format=rss
  • VG247       – https://www.vg247.com/feed
  • GameSpot    – https://www.gamespot.com/feeds/mashup/
"""
from __future__ import annotations
import re
from typing import List, Tuple

import aiohttp
import feedparser

from parsers.base import BaseParser, NewsItem

MARATHON_KEYWORDS = [
    "marathon bungie", "marathon game", "marathon extraction",
    "#marathon", "marathon fps", "marathon shooter",
    "bungie marathon", "marathon 2026",
]

FEEDS: List[Tuple[str, str]] = [
    ("IGN",       "https://feeds.feedburner.com/ign/all"),
    ("PCGamer",   "https://www.pcgamer.com/rss/"),
    ("GamesRadar","https://www.gamesradar.com/rss/"),
    ("Kotaku",    "https://kotaku.com/rss"),
    ("Eurogamer", "https://www.eurogamer.net/?format=rss"),
    ("VG247",     "https://www.vg247.com/feed"),
    ("GameSpot",  "https://www.gamespot.com/feeds/mashup/"),
    ("Polygon",   "https://www.polygon.com/rss/index.xml"),
]


class GamingNewsParser(BaseParser):
    SOURCE_NAME = "Gaming News"
    SOURCE_KEY = "gaming_news"

    async def fetch(self) -> List[NewsItem]:
        import asyncio
        tasks = [self._fetch_feed(name, url) for name, url in FEEDS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        items: List[NewsItem] = []
        for result in results:
            if isinstance(result, list):
                items.extend(result)
        return items

    async def _fetch_feed(self, outlet_name: str, feed_url: str) -> List[NewsItem]:
        items: List[NewsItem] = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    feed_url,
                    timeout=aiohttp.ClientTimeout(total=12),
                    headers={"User-Agent": "MarathonNewsBot/1.0"},
                ) as resp:
                    if resp.status != 200:
                        return items
                    content = await resp.text()

            feed = feedparser.parse(content)
            for entry in feed.entries:
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                body = _strip_html(summary)

                # Only include Marathon-relevant articles
                searchable = (title + " " + body).lower()
                if not _is_marathon_related(searchable):
                    continue

                url = entry.get("link", "")
                item_id = url or entry.get("id", title)
                published = entry.get("published", "")
                author = entry.get("author", outlet_name)

                # Extract images from summary HTML
                media = re.findall(
                    r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|gif|webp)',
                    summary
                )

                items.append(NewsItem(
                    source=f"{self.SOURCE_NAME} – {outlet_name}",
                    source_key=f"{self.SOURCE_KEY}_{outlet_name.lower()}",
                    item_id=item_id,
                    title=title,
                    url=url,
                    body=body[:1500],
                    published=published,
                    author=author,
                    media_urls=list(dict.fromkeys(media)),
                ))
        except Exception as exc:
            self.logger.debug("%s feed error: %s", outlet_name, exc)
        return items


def _is_marathon_related(text: str) -> bool:
    return any(kw in text for kw in MARATHON_KEYWORDS)


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()
