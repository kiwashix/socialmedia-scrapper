"""
parsers/twitter.py – Pulls tweets from @MarathonTheGame via public Nitter RSS feeds.

Nitter is an open-source Twitter front-end with RSS support that doesn't require
API keys. We try several public Nitter instances and fall back gracefully if all
are down.

NOTE: If you have access to the official Twitter/X API v2 (Basic tier ~$100/mo),
replace the `_fetch_nitter` method with an authenticated API call.
"""
from __future__ import annotations
import re
from typing import List

import aiohttp
import feedparser

from parsers.base import BaseParser, NewsItem

TWITTER_HANDLE = "MarathonTheGame"

# Public Nitter instances – we try them in order
NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.net",
    "https://nitter.1d4.us",
]


class TwitterParser(BaseParser):
    SOURCE_NAME = "Twitter @MarathonTheGame"
    SOURCE_KEY = "twitter"

    async def fetch(self) -> List[NewsItem]:
        for instance in NITTER_INSTANCES:
            items = await self._fetch_nitter(instance)
            if items is not None:
                return items
        self.logger.warning(
            "All Nitter instances failed. Twitter feed unavailable. "
            "Consider using the official Twitter API."
        )
        return []

    async def _fetch_nitter(self, instance: str) -> List[NewsItem] | None:
        url = f"{instance}/{TWITTER_HANDLE}/rss"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=10),
                    headers={"User-Agent": "MarathonNewsBot/1.0"},
                ) as resp:
                    if resp.status != 200:
                        return None
                    content = await resp.text()

            feed = feedparser.parse(content)
            if not feed.entries:
                return None

            items: List[NewsItem] = []
            for entry in feed.entries:
                tweet_url = _normalize_url(entry.get("link", ""), instance)
                tweet_id = _extract_tweet_id(tweet_url)
                if not tweet_id:
                    continue

                title = entry.get("title", "")
                summary = entry.get("summary", "")
                body = _strip_html(summary)
                published = entry.get("published", "")

                media = _extract_media_from_summary(summary)

                items.append(NewsItem(
                    source=self.SOURCE_NAME,
                    source_key=self.SOURCE_KEY,
                    item_id=tweet_id,
                    title=title[:200],
                    url=f"https://x.com/{TWITTER_HANDLE}/status/{tweet_id}",
                    body=body[:1000],
                    published=published,
                    author=f"@{TWITTER_HANDLE}",
                    media_urls=media,
                ))
            return items
        except Exception as exc:
            self.logger.debug("Nitter instance %s failed: %s", instance, exc)
            return None


# ─── helpers ─────────────────────────────────────────────────────────────────

def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _normalize_url(url: str, instance: str) -> str:
    """Replace the nitter instance domain with the real twitter.com domain."""
    # nitter URLs look like https://nitter.net/MarathonTheGame/status/12345
    for inst in NITTER_INSTANCES:
        url = url.replace(inst.rstrip("/"), "https://x.com")
    url = url.replace(instance.rstrip("/"), "https://x.com")
    return url


def _extract_tweet_id(url: str) -> str:
    m = re.search(r"/status/(\d+)", url)
    return m.group(1) if m else ""


def _extract_media_from_summary(html: str) -> List[str]:
    """Pull img src values out of the RSS summary HTML."""
    return re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html)
