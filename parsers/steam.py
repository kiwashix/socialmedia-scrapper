"""
parsers/steam.py – Watches the Steam store news feed for Marathon (App ID 3065800).
Steam provides a public news RSS/JSON endpoint for every game – no auth required.
"""
from __future__ import annotations
from typing import List

import aiohttp

from parsers.base import BaseParser, NewsItem

MARATHON_APP_ID = 3065800
STEAM_NEWS_URL = (
    f"https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"
    f"?appid={MARATHON_APP_ID}&count=20&maxlength=1500&format=json"
)


class SteamParser(BaseParser):
    SOURCE_NAME = "Steam – Marathon"
    SOURCE_KEY = "steam"

    async def fetch(self) -> List[NewsItem]:
        items: List[NewsItem] = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    STEAM_NEWS_URL,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        self.logger.warning("Steam API returned %s", resp.status)
                        return items
                    data = await resp.json()

            news_items = (
                data.get("appnews", {}).get("newsitems", [])
            )
            for entry in news_items:
                gid = str(entry.get("gid", ""))
                title = entry.get("title", "")
                url = entry.get("url", "")
                body = entry.get("contents", "")[:1500]
                author = entry.get("author", "")
                date = _ts(entry.get("date", 0))

                # Extract image URLs from contents (Steam uses BBCode-ish HTML)
                import re
                media = re.findall(r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|gif|webp)', body)

                items.append(NewsItem(
                    source=self.SOURCE_NAME,
                    source_key=self.SOURCE_KEY,
                    item_id=gid,
                    title=title,
                    url=url,
                    body=body,
                    published=date,
                    author=author,
                    media_urls=list(dict.fromkeys(media)),  # deduplicate, keep order
                ))
        except Exception as exc:
            self.logger.error("SteamParser error: %s", exc, exc_info=True)
        return items


def _ts(utc_ts) -> str:
    from datetime import datetime, timezone
    try:
        return datetime.fromtimestamp(int(utc_ts), tz=timezone.utc).isoformat()
    except Exception:
        return ""
