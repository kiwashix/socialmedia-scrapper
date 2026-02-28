"""
parsers/reddit.py – Pulls top/new posts from r/Marathon using httpx + BeautifulSoup.

This parser uses the old.reddit.com HTML pages (no API key required).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List

import httpx
from bs4 import BeautifulSoup

from config import REDDIT_MIN_SCORE
from parsers.base import BaseParser, NewsItem


SUBREDDIT = "Marathon"


@dataclass
class RedditPost:
    id: str
    title: str
    url: str
    score: int
    published: str


HEADERS_SUB = {
    "User-Agent": "Mozilla/5.0 (TelegramRedditBot/1.0)"
}

HEADERS_POST = {
    "User-Agent": "Mozilla/5.0 (TelegramWebView/1.0)"
}


def parse_subreddit(sub: str) -> List[RedditPost]:
    """Parse new posts from a subreddit using old.reddit.com HTML."""
    url = f"https://old.reddit.com/r/{sub}/new"

    with httpx.Client(timeout=10.0, headers=HEADERS_SUB, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    posts: List[RedditPost] = []

    for thing in soup.select(".thing"):
        post_id = thing.get("data-fullname")
        title_tag = thing.select_one("a.title")
        score_tag = thing.select_one(".score")
        published = thing.select_one("time.live-timestamp")

        if not post_id or not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        link = title_tag.get("href", "")

        score_text = score_tag.get_text(strip=True) if score_tag else "0"
        try:
            score = int(score_text)
        except ValueError:
            score = 0

        posts.append(
            RedditPost(
                id=post_id,
                title=title,
                url=link,
                score=score,
                published=published
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

    with httpx.Client(
        timeout=10.0,
        headers=HEADERS_POST,
        follow_redirects=True
    ) as client:
        resp = client.get(post_url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    body = soup.select_one("div.entry div.usertext-body div.md")
    if not body:
        body = soup.select_one("div.usertext-body div.md")

    if not body:
        raise ValueError("post has no selftext")

    lines = [
        p.get_text(strip=True)
        for p in body.find_all("p")
        if p.get_text(strip=True)
    ]

    if not lines:
        text = body.get_text(strip=True)
        if text:
            lines = [text]

    return "\n\n".join(lines)


class RedditParser(BaseParser):
    """Parser for Reddit r/Marathon posts."""
    
    SOURCE_NAME = "Reddit r/Marathon"
    SOURCE_KEY = "reddit"

    async def fetch(self) -> List[NewsItem]:
        """Fetch new posts from r/Marathon."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_sync)

    def _fetch_sync(self) -> List[NewsItem]:
        """Fetch posts synchronously (run in thread pool)."""
        items: List[NewsItem] = []
        
        try:
            posts = parse_subreddit(SUBREDDIT)
            
            for post in posts:
                # Filter by minimum score
                if post.score < REDDIT_MIN_SCORE:
                    continue
                
                # Normalize the URL
                post_url = normalize_post_url(post.url)
                if not post_url.startswith("http"):
                    post_url = f"https://old.reddit.com{post.url}"
                
                # Build the full Reddit URL for the post
                full_url = post_url
                if not full_url.startswith("http"):
                    full_url = f"https://old.reddit.com{post.url}"
                
                # Try to get the post body
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
                    url=full_url,
                    body=body[:1500] if body else "",
                    published="",  # HTML parsing doesn't provide easy timestamp
                    author="",     # Would need additional parsing
                    media_urls=[],
                    score=post.score,
                    tags=[],
                ))
                
        except Exception as exc:
            self.logger.error("Reddit parsing error: %s", exc, exc_info=True)
        
        return items
