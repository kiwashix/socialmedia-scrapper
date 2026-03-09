"""
parsers/twitter.py — Парсит твиты через внутренний GraphQL API X (Twitter).

Использует публичный Bearer-токен и guest-токен (как браузер без авторизации).
Не требует аккаунта и API-ключей.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import List, Optional

import aiohttp

from parsers.base import BaseParser, NewsItem

logger = logging.getLogger(__name__)

BEARER_TOKEN = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

BASE_HEADERS = {
    "authorization": f"Bearer {BEARER_TOKEN}",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "x-twitter-active-user": "yes",
    "x-twitter-client-language": "en",
    "accept": "*/*",
    "referer": "https://twitter.com/",
}

GUEST_ACTIVATE_URL = "https://api.twitter.com/1.1/guest/activate.json"

USER_BY_SCREEN_NAME_URL = (
    "https://twitter.com/i/api/graphql/G3KGOASz96M-Qu0nwmGXNg/UserByScreenName"
)

USER_TWEETS_URL = (
    "https://twitter.com/i/api/graphql/V7H0Ap3_Hh2FyS75OCDO3Q/UserTweets"
)

TIMEOUT = aiohttp.ClientTimeout(total=20)

_guest_token: Optional[str] = None
_guest_token_lock = asyncio.Lock()


async def _get_guest_token(session: aiohttp.ClientSession) -> Optional[str]:
    global _guest_token

    async with _guest_token_lock:
        if _guest_token:
            return _guest_token

        try:
            async with session.post(
                GUEST_ACTIVATE_URL,
                headers={
                    "authorization": f"Bearer {BEARER_TOKEN}",
                    "user-agent": "Mozilla/5.0",
                },
                timeout=TIMEOUT,
            ) as resp:

                if resp.status != 200:
                    logger.error("Twitter guest activate → HTTP %d", resp.status)
                    return None

                data = await resp.json()
                _guest_token = data.get("guest_token")

                if _guest_token:
                    logger.info(
                        "Twitter guest token acquired: %s...",
                        _guest_token[:8],
                    )

                return _guest_token

        except Exception as exc:
            logger.error("Twitter guest token error: %s", exc)
            return None


async def _get_user_id(
    session: aiohttp.ClientSession,
    handle: str,
    auth_headers: dict,
) -> Optional[str]:

    params = {
        "variables": json.dumps({
            "screen_name": handle,
            "withSafetyModeUserFields": True,
        })
    }

    try:
        async with session.get(
            USER_BY_SCREEN_NAME_URL,
            headers=auth_headers,
            params=params,
            timeout=TIMEOUT,
        ) as resp:

            if resp.status != 200:
                logger.warning(
                    "Twitter UserByScreenName @%s → HTTP %d",
                    handle,
                    resp.status,
                )
                return None

            data = await resp.json()

            result = (
                data.get("data", {})
                .get("user", {})
                .get("result")
            )

            if not result:
                return None

            return result.get("rest_id")

    except Exception as exc:
        logger.warning(
            "Twitter UserByScreenName @%s error: %s",
            handle,
            exc,
        )
        return None


async def _get_tweets(
    session: aiohttp.ClientSession,
    user_id: str,
    auth_headers: dict,
    count: int = 10,
) -> list:

    params = {
        "variables": json.dumps({
            "userId": user_id,
            "count": count,
            "includePromotedContent": False,
            "withVoice": True,
        })
    }

    try:
        async with session.get(
            USER_TWEETS_URL,
            headers=auth_headers,
            params=params,
            timeout=TIMEOUT,
        ) as resp:

            if resp.status != 200:
                logger.warning(
                    "Twitter UserTweets %s → HTTP %d",
                    user_id,
                    resp.status,
                )
                return []

            data = await resp.json()

            instructions = (
                data.get("data", {})
                .get("user", {})
                .get("result", {})
                .get("timeline", {})
                .get("timeline", {})
                .get("instructions", [])
            )

            return instructions

    except Exception as exc:
        logger.warning(
            "Twitter UserTweets %s error: %s",
            user_id,
            exc,
        )
        return []


def _parse_instructions(instructions: list) -> list[dict]:

    tweets = []

    for instr in instructions:
        for entry in instr.get("entries", []):

            item = entry.get("content", {}).get("itemContent")
            if not item:
                continue

            result = item.get("tweet_results", {}).get("result")
            if not result:
                continue

            legacy = result.get("legacy")
            if not legacy:
                continue

            tweet_id = legacy.get("id_str") or result.get("rest_id")
            text = legacy.get("full_text", "")

            tweets.append({
                "id": tweet_id,
                "text": text,
                "created_at": legacy.get("created_at"),
                "is_retweet": text.startswith("RT @"),
                "reply_to": legacy.get("in_reply_to_screen_name"),
                "media": [
                    m.get("media_url_https")
                    for m in legacy.get("entities", {}).get("media", [])
                ],
            })

    return tweets


class TwitterParser(BaseParser):

    def __init__(self, source_config: dict):
        super().__init__()

        self.config = source_config
        self.SOURCE_NAME = source_config["id"]
        self.SOURCE_KEY = f"{source_config['type']}:{source_config['id']}"
        self.handle = source_config["username"]

    async def fetch(self) -> List[NewsItem]:

        async with aiohttp.ClientSession() as session:

            guest_token = await _get_guest_token(session)
            if not guest_token:
                logger.warning(
                    "Twitter: no guest token, skipping @%s",
                    self.handle,
                )
                return []

            auth_headers = {
                **BASE_HEADERS,
                "x-guest-token": guest_token,
            }

            user_id = await _get_user_id(
                session,
                self.handle,
                auth_headers,
            )

            if not user_id:
                logger.warning(
                    "Twitter: user @%s not found",
                    self.handle,
                )
                return []

            instructions = await _get_tweets(
                session,
                user_id,
                auth_headers,
            )

        raw_tweets = _parse_instructions(instructions)

        items: List[NewsItem] = []

        for tw in raw_tweets:

            if tw["is_retweet"]:
                continue

            if tw["reply_to"]:
                continue

            items.append(
                NewsItem(
                    source=self.SOURCE_NAME,
                    source_key=self.SOURCE_KEY,
                    item_id=tw["id"],
                    title=tw["text"][:200],
                    url=f"https://x.com/{self.handle}/status/{tw['id']}",
                    body=tw["text"][:1000],
                    published=tw["created_at"],
                    author=f"@{self.handle}",
                    media_urls=[m for m in tw["media"] if m],
                )
            )

        logger.info(
            "TwitterParser @%s → %d tweets",
            self.handle,
            len(items),
        )

        return items