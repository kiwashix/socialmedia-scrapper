"""
parsers/bungie.py – Pulls Marathon-related news from Bungie.net.

ИСПРАВЛЕНИЯ:
  - Убран пустой "X-API-Key": "" заголовок (пустой ключ может дать 403)
  - Добавлен браузерный User-Agent
"""
from __future__ import annotations
import hashlib
import re
from typing import List

import aiohttp
from bs4 import BeautifulSoup

from parsers.base import BaseParser, NewsItem

BUNGIE_API_URL = (
    "https://www.bungie.net/Platform/Content/SearchContentWithText/"
    "?searchtext=marathon&head=false&types=News&currentpage=1&itemsperpage=15"
)
BUNGIE_BASE = "https://www.bungie.net"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


class BungieParser(BaseParser):
    SOURCE_NAME = "Bungie.net News"
    SOURCE_KEY = "bungie"

    async def fetch(self) -> List[NewsItem]:
        items: List[NewsItem] = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    BUNGIE_API_URL,
                    headers=HEADERS,  # ✅ без пустого X-API-Key
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        self.logger.warning("Bungie API returned %s", resp.status)
                        return items
                    data = await resp.json(content_type=None)

            results = (
                data.get("Response", {})
                    .get("results", {})
                    .get("results", [])
            )
            for entry in results:
                title = entry.get("properties", {}).get("Title", "")
                subtitle = entry.get("properties", {}).get("Subtitle", "")
                url_path = entry.get("url", "")
                if not url_path.startswith("http"):
                    url_path = BUNGIE_BASE + url_path
                item_id = entry.get("contentId", hashlib.md5(url_path.encode()).hexdigest())
                date = entry.get("creationDate", "")

                html_body = entry.get("properties", {}).get("Content", "")
                body = _html_to_text(html_body)[:1500]

                media: List[str] = []
                banner = entry.get("properties", {}).get("LargeImage", "")
                if banner:
                    if not banner.startswith("http"):
                        banner = BUNGIE_BASE + banner
                    media.append(banner)

                items.append(NewsItem(
                    source=self.SOURCE_NAME,
                    source_key=self.SOURCE_KEY,
                    item_id=str(item_id),
                    title=title,
                    url=url_path,
                    body=f"{subtitle}\n\n{body}".strip(),
                    published=date,
                    media_urls=media,
                ))
        except Exception as exc:
            self.logger.error("BungieParser error: %s", exc, exc_info=True)
        return items


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text.strip()