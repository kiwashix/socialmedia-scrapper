"""
parsers/reddit.py – Pulls new posts from subreddits using old.reddit.com HTML.
"""
from __future__ import annotations
import asyncio
import time
import random
from dataclasses import dataclass
from typing import List

import httpx
from bs4 import BeautifulSoup

from core.config import REDDIT_MIN_SCORE
from parsers.base import BaseParser, NewsItem


@dataclass
class RedditPost:
    id: str
    title: str
    url: str
    score: int
    published: str  # ISO datetime string from <time datetime="...">


# Разные User-Agent'ы для ротации — снижает вероятность блокировки
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

# Задержка между запросами к Reddit (секунды)
_REQUEST_DELAY_MIN = 1.5
_REQUEST_DELAY_MAX = 3.0


def _random_ua() -> str:
    return random.choice(_USER_AGENTS)


def _sleep_between_requests():
    """Блокирующий sleep для thread pool."""
    time.sleep(random.uniform(_REQUEST_DELAY_MIN, _REQUEST_DELAY_MAX))


def parse_subreddit(sub: str) -> List[RedditPost]:
    """Parse new posts from a subreddit using old.reddit.com HTML."""
    url = f"https://old.reddit.com/r/{sub}/new"

    with httpx.Client(
        timeout=15.0,
        headers={"User-Agent": _random_ua()},
        follow_redirects=True,
    ) as client:
        resp = client.get(url)

    if resp.status_code == 403:
        raise PermissionError(f"Reddit 403 Forbidden for r/{sub} — rate limited or blocked")
    if resp.status_code == 429:
        raise PermissionError(f"Reddit 429 Too Many Requests for r/{sub}")
    if resp.status_code != 200:
        raise ConnectionError(f"Reddit HTTP {resp.status_code} for r/{sub}")

    soup = BeautifulSoup(resp.text, "html.parser")
    posts: List[RedditPost] = []

    for thing in soup.select(".thing"):
        post_id = thing.get("data-fullname")
        title_tag = thing.select_one("a.title")
        score_tag = thing.select_one(".score.unvoted") or thing.select_one(".score")
        time_tag = thing.select_one("time.live-timestamp")

        if not post_id or not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        link = title_tag.get("href", "")

        score_text = score_tag.get_text(strip=True) if score_tag else "0"
        try:
            score = int(score_text.replace(",", ""))
        except ValueError:
            score = 0

        # Извлекаем ISO datetime из атрибута тега <time>
        published = ""
        if time_tag:
            published = time_tag.get("datetime", "") or ""

        posts.append(
            RedditPost(
                id=post_id,
                title=title,
                url=link,
                score=score,
                published=published,
            )
        )

    return posts


def normalize_post_url(url: str) -> str:
    """Normalize a Reddit URL to old.reddit.com format."""
    if url.startswith("/"):
        return "https://old.reddit.com" + url
    if url.startswith("https://www.reddit.com"):
        return url.replace("https://www.reddit.com", "https://old.reddit.com")
    if url.startswith("https://reddit.com"):
        return url.replace("https://reddit.com", "https://old.reddit.com")
    return url


def parse_post_body(post_url: str) -> str:
    """Parse the selftext body from a Reddit post."""
    post_url = normalize_post_url(post_url)

    try:
        with httpx.Client(
            timeout=12.0,
            headers={"User-Agent": _random_ua()},
            follow_redirects=True,
        ) as client:
            resp = client.get(post_url)
    except httpx.ConnectError as e:
        raise ConnectionError(f"connection error: {e}") from None
    except httpx.TimeoutException:
        raise TimeoutError("timeout fetching post body") from None

    if resp.status_code in (403, 429):
        raise PermissionError(f"HTTP {resp.status_code} fetching post body")
    if resp.status_code != 200:
        raise ConnectionError(f"HTTP {resp.status_code} fetching post body")

    soup = BeautifulSoup(resp.text, "html.parser")
    body = soup.select_one("div.entry div.usertext-body div.md") or \
           soup.select_one("div.usertext-body div.md")

    if not body:
        raise ValueError("post has no selftext")

    lines = [p.get_text(strip=True) for p in body.find_all("p") if p.get_text(strip=True)]
    if not lines:
        text = body.get_text(strip=True)
        if text:
            lines = [text]

    return "\n\n".join(lines)


class RedditParser(BaseParser):
    """Parser for Reddit posts."""

    def __init__(self, source_config: dict):
        super().__init__()
        self.config = source_config
        self.SOURCE_NAME = source_config['id']
        self.SOURCE_KEY = f"{source_config['type']}:{source_config['id']}"
        self.SUBREDDIT = source_config['subreddit']

    async def fetch(self) -> List[NewsItem]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_sync)

    def _fetch_sync(self) -> List[NewsItem]:
        items: List[NewsItem] = []

        try:
            posts = parse_subreddit(self.SUBREDDIT)

            for post in posts:
                if post.score < REDDIT_MIN_SCORE:
                    continue

                post_url = normalize_post_url(post.url)
                if not post_url.startswith("http"):
                    post_url = f"https://old.reddit.com{post.url}"

                # Задержка между запросами тела — избегаем 403
                _sleep_between_requests()

                body = ""
                try:
                    body = parse_post_body(post_url)
                except Exception as e:
                    self.logger.debug("Could not fetch post body for %s: %s", post.id, e)

                items.append(NewsItem(
                    source=self.SOURCE_NAME,
                    source_key=self.SOURCE_KEY,
                    item_id=post.id,
                    title=post.title,
                    url=post_url,
                    body=body[:1500] if body else "",
                    published=post.published,  # ← теперь реальная дата
                    author="",
                    media_urls=[],
                    score=post.score,
                    tags=[],
                ))

        except PermissionError as exc:
            # 403/429 от Reddit — короткий warning без трейсбека
            self.logger.warning("Reddit blocked r/%s: %s", self.SUBREDDIT, exc)
        except ConnectionError as exc:
            self.logger.warning("Reddit connection error r/%s: %s", self.SUBREDDIT, exc)
        except Exception as exc:
            self.logger.error("Reddit parsing error r/%s: %s", self.SUBREDDIT, exc)

        return items
