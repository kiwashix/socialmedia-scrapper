"""
main.py – Entry point for the Marathon News Bot.

ИЗМЕНЕНИЯ:
  - Новости сортируются по дате публикации (published) перед отправкой
    → сначала старые, чтобы в Telegram лента шла в хронологическом порядке
  - mark_processed теперь сохраняет published дату
  - Вспомогательная функция _parse_date для унификации форматов дат
"""
from __future__ import annotations
import asyncio
import logging
import sys
from datetime import datetime, timezone
from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

import config
import database
from ai_processor import process_item, ProcessedItem
from parsers import __all__
from telegram_sender import TelegramSender

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("marathon_bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")

sender = TelegramSender()


def _parse_date(date_str: str) -> datetime:
    """
    Парсит строку даты в datetime. Возвращает epoch (1970) если не удалось.
    Поддерживает ISO-8601 и RFC-2822 (Reddit/RSS).
    """
    if not date_str:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    # ISO-8601 (Steam, Bungie, Reddit JSON)
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(date_str[:25], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
    # RFC-2822 (RSS feeds: "Mon, 02 Jan 2006 15:04:05 +0000")
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str)
    except Exception:
        pass
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


async def run_news_cycle() -> None:
    logger.info("─── Starting news cycle (%s) ───", datetime.utcnow().isoformat())

    # 1. Fetch от всех источников параллельно
    tasks = [parser_cls().fetch() for parser_cls in __all__]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_items = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning("Parser %s raised: %s", __all__[i].SOURCE_NAME, result)
        else:
            all_items.extend(result)

    logger.info("Fetched %d total items across all sources.", len(all_items))

    # 2. Фильтр уже обработанных
    new_items = [
        item for item in all_items
        if not database.is_processed(item.source_key, item.item_id)
    ]
    logger.info("%d new (unprocessed) items to evaluate.", len(new_items))

    if not new_items:
        logger.info("Nothing new. Sleeping until next cycle.")
        return

    # ✅ Сортировка по дате публикации (от старых к новым)
    # Так в Telegram лента идёт в хронологическом порядке
    new_items.sort(key=lambda item: _parse_date(item.published))
    logger.info("Items sorted by published date (oldest first).")

    # Лимит на количество за один цикл
    new_items = new_items[: config.MAX_ITEMS_PER_RUN * len(__all__)]

    # 3. AI-обработка параллельно (семафор = защита от rate limit)
    semaphore = asyncio.Semaphore(5)

    async def process_with_semaphore(item):
        async with semaphore:
            return await process_item(item)

    processed_results = await asyncio.gather(
        *[process_with_semaphore(item) for item in new_items],
        return_exceptions=True,
    )

    relevant: List[ProcessedItem] = []
    for i, result in enumerate(processed_results):
        item = new_items[i]
        if isinstance(result, Exception):
            logger.warning("AI error for '%s': %s", item.title, result)
            # ✅ Сохраняем published дату
            database.mark_processed(
                item.source_key, item.item_id, item.url, item.title, item.published
            )
        elif result is not None:
            # ✅ Сохраняем published дату
            database.mark_processed(
                item.source_key, item.item_id, item.url, item.title, item.published
            )
            if result.is_relevant:
                relevant.append(result)
            else:
                logger.info("AI filtered out (not relevant): '%s'", item.title)

    logger.info("%d items passed AI relevance filter.", len(relevant))

    if relevant:
        sent = await sender.send_batch(relevant, delay=2.0)
        logger.info("Sent %d/%d messages to Telegram.", sent, len(relevant))
    else:
        logger.info("No relevant items to send.")

    logger.info("─── Cycle complete ───")


async def main() -> None:
    logger.info("Marathon News Bot initialising…")

    database.init_db()
    stats = database.get_stats()
    logger.info("DB stats: %s", stats)

    try:
        await sender.send_startup_message()
    except Exception as exc:
        logger.error("Could not send startup message: %s", exc)

    await run_news_cycle()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_news_cycle,
        trigger=IntervalTrigger(minutes=config.POLL_INTERVAL_MINUTES),
        id="news_cycle",
        name="Marathon News Cycle",
        misfire_grace_time=60,
    )
    scheduler.start()
    logger.info(
        "Scheduler started. Checking every %d minute(s).",
        config.POLL_INTERVAL_MINUTES,
    )

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down…")
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())