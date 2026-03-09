from parsers.base import BaseParser, NewsItem
import asyncio
from typing import List
import feedparser

class RSSParser(BaseParser):

    def __init__(self, source_config: dict):
        super().__init__()

        self.config = source_config
        self.feed_url = source_config["url"]

        self.SOURCE_NAME = source_config["id"]
        self.SOURCE_KEY = f"{source_config['type']}:{source_config['id']}"

    async def fetch(self) -> List[NewsItem]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_sync)

    def _fetch_sync(self) -> List[NewsItem]:

        items: List[NewsItem] = []

        try:
            feed = feedparser.parse(self.feed_url)

            for entry in feed.entries:

                item_id = entry.get("id") or entry.get("link")

                title = entry.get("title", "")
                url = entry.get("link", "")

                body = entry.get("summary", "")
                body = body[:1500] if body else ""

                published = entry.get("published", "")
                author = entry.get("author", "")

                media_urls = []

                if "media_content" in entry:
                    for media in entry.media_content:
                        if "url" in media:
                            media_urls.append(media["url"])

                items.append(
                    NewsItem(
                        source=self.SOURCE_NAME,
                        source_key=self.SOURCE_KEY,
                        item_id=item_id,
                        title=title,
                        url=url,
                        body=body,
                        published=published,
                        author=author,
                        media_urls=media_urls,
                        score=0,
                        tags=[],
                    )
                )

        except Exception as exc:
            self.logger.error(
                "RSS parsing error: %s",
                exc,
                exc_info=True
            )

        return items