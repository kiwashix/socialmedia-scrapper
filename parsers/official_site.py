"""
parsers/official_site.py – Scrapes news/updates from marathonthegame.com.
This is a lightweight scraper that looks for a news or updates section.
"""
from __future__ import annotations
import hashlib
import re
from typing import List

import aiohttp
from bs4 import BeautifulSoup

from parsers.base import BaseParser, NewsItem

OFFICIAL_SITE = "https://www.marathonthegame.com"


class OfficialSiteParser(BaseParser):
    SOURCE_NAME = "marathonthegame.com"
    SOURCE_KEY = "official_site"

    async def fetch(self) -> List[NewsItem]:
        items: List[NewsItem] = []
        try:
            async with aiohttp.ClientSession() as session:
                # Try the news or updates page first, fall back to main page
                for path in ["/news", "/updates", "/blog", "/"]:
                    url = OFFICIAL_SITE + path
                    async with session.get(
                        url,
                        timeout=aiohttp.ClientTimeout(total=15),
                        headers={"User-Agent": "MarathonNewsBot/1.0"},
                        allow_redirects=True,
                    ) as resp:
                        if resp.status == 200:
                            html = await resp.text()
                            found = self._parse_html(html, url)
                            if found:
                                items.extend(found)
                                break
        except Exception as exc:
            self.logger.error("OfficialSiteParser error: %s", exc, exc_info=True)
        return items

    def _parse_html(self, html: str, source_url: str) -> List[NewsItem]:
        """Best-effort extraction of article cards from the official site."""
        items: List[NewsItem] = []
        soup = BeautifulSoup(html, "lxml")

        # Look for article / card elements
        cards = soup.find_all(
            ["article", "div"],
            class_=re.compile(r"(news|update|post|card|blog)", re.I),
        )

        for card in cards[:10]:
            a_tag = card.find("a", href=True)
            if not a_tag:
                continue
            href = a_tag["href"]
            if not href.startswith("http"):
                href = OFFICIAL_SITE + href

            title_el = card.find(re.compile(r"h[1-4]"))
            title = title_el.get_text(strip=True) if title_el else a_tag.get_text(strip=True)
            if not title:
                continue

            img = card.find("img")
            media: List[str] = []
            if img and img.get("src"):
                src = img["src"]
                if not src.startswith("http"):
                    src = OFFICIAL_SITE + src
                media.append(src)

            body_el = card.find("p")
            body = body_el.get_text(strip=True) if body_el else ""

            item_id = hashlib.md5(href.encode()).hexdigest()[:16]
            items.append(NewsItem(
                source=self.SOURCE_NAME,
                source_key=self.SOURCE_KEY,
                item_id=item_id,
                title=title,
                url=href,
                body=body[:1000],
                published="",
                media_urls=media,
            ))

        return items
