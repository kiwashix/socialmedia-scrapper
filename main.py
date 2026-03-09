from __future__ import annotations
import asyncio
import logging
import sys
import random
from datetime import datetime, timezone
from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from core import database, config
from core.ai_processor import process_item, ProcessedItem
from utils.date_util import is_recent, is_today, _parse_date
from utils.builder import build_parsers
from telegram_sender import TelegramSender

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("network_bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")

sender = TelegramSender()


async def run_news_cycle() -> None:
    logger.info("─── Starting news cycle (%s) ───", datetime.now(timezone.utc).isoformat())

    # 1️⃣ Строим парсеры из YAML
    parsers_by_game: dict[str, list] = {}
    for game, yaml_data in config.SOURCES_YAML.items():
        parsers_by_game[game] = build_parsers(yaml_data)

    # Плоский список всех парсеров
    all_parsers = [p for game_parsers in parsers_by_game.values() for p in game_parsers]

    # 2️⃣ Fetch от всех источников
    all_items = []

    twitter_parsers = [p for p in all_parsers if p.SOURCE_KEY.startswith("twitter:")]
    reddit_parsers = [p for p in all_parsers if p.SOURCE_KEY.startswith("reddit:")]
    other_parsers = [
        p
        for p in all_parsers
        if not p.SOURCE_KEY.startswith("reddit:")
        and not p.SOURCE_KEY.startswith("twitter:")
    ]

    # Параллельный fetch для RSS / YouTube / Steam
    if other_parsers:
        other_results = await asyncio.gather(
            *[p.fetch() for p in other_parsers], return_exceptions=True
        )
        for parser, result in zip(other_parsers, other_results):
            if isinstance(result, Exception):
                logger.warning("Parser %s raised: %s", parser.SOURCE_NAME, result)
            elif result:
                all_items.extend(result)
                logger.info("Parser %s fetched %d items", parser.SOURCE_NAME, len(result))

    # Последовательный fetch для Reddit
    for i, parser in enumerate(reddit_parsers):
        if i > 0:
            delay = random.uniform(6.0, 12.0)
            logger.debug("Reddit delay %.1fs before %s", delay, parser.SOURCE_NAME)
            await asyncio.sleep(delay)

        try:
            result = await parser.fetch()
            if result:
                all_items.extend(result)
                logger.info("Parser %s fetched %d items", parser.SOURCE_NAME, len(result))
        except Exception as e:
            logger.warning("Parser %s raised: %s", parser.SOURCE_NAME, e)

    # Последовательный fetch для Twitter
    for i, parser in enumerate(twitter_parsers):
        if i > 0:
            delay = random.uniform(2.0, 4.0)
            await asyncio.sleep(delay)

        try:
            result = await parser.fetch()
            if result:
                all_items.extend(result)
                logger.info("Parser %s fetched %d items", parser.SOURCE_NAME, len(result))
        except Exception as e:
            logger.warning("Parser %s raised: %s", parser.SOURCE_NAME, e)

    logger.info("Fetched %d total items across all sources.", len(all_items))

    # 3️⃣ Фильтр новых
    new_items: list = []
    for game, parsers in parsers_by_game.items():
        for parser in parsers:
            key = f"{parser.SOURCE_KEY}:{parser.SOURCE_NAME}"
            last_date = config.LAST_PROCESSED_DATE[game].get(
                key, datetime(1970, 1, 1, tzinfo=timezone.utc)
            )
            items_source = [
                item
                for item in all_items
                if item.source_key == parser.SOURCE_KEY
                and not database.is_processed(item.source_key, item.item_id)
                and _parse_date(item.published) > last_date
                and is_today(item.published)
            ]
            if items_source:
                latest = max(_parse_date(i.published) for i in items_source)
                config.LAST_PROCESSED_DATE[game][key] = latest

            new_items.extend(items_source[: config.MAX_PER_SOURCE])

    logger.info("%d new (unprocessed) items to evaluate.", len(new_items))

    if not new_items:
        logger.info("Nothing new. Sleeping until next cycle.")
        return

    # 4️⃣ Сортировка
    new_items.sort(key=lambda item: _parse_date(item.published))
    logger.info("Items sorted by published date (oldest first).")
    new_items = new_items[: config.MAX_ITEMS_PER_RUN]

    # 5️⃣ AI обработка
    semaphore = asyncio.Semaphore(2)

    async def process_with_semaphore(item):
        async with semaphore:
            await asyncio.sleep(3)
            return await process_item(item)

    processed_results = await asyncio.gather(
        *[process_with_semaphore(item) for item in new_items],
        return_exceptions=True,
    )

    # 6️⃣ Фильтрация
    relevant: List[ProcessedItem] = []
    for i, result in enumerate(processed_results):
        item = new_items[i]
        if isinstance(result, Exception):
            logger.warning("AI error for '%s': %s", item.title, result)
            database.mark_processed(
                item.source_key, item.item_id, item.url, item.title, item.published
            )
        elif result is not None:
            database.mark_processed(
                item.source_key, item.item_id, item.url, item.title, item.published
            )
            if result.is_relevant:
                relevant.append(result)
            else:
                logger.info("AI filtered out (not relevant): '%s'", item.title)

    logger.info("%d items passed AI relevance filter.", len(relevant))

    # 7️⃣ Отправка в Telegram
    if relevant:
        sent = await sender.send_batch(relevant, delay=2.0)
        logger.info("Sent %d/%d messages to Telegram.", sent, len(relevant))
    else:
        logger.info("No relevant items to send.")

    logger.info("─── Cycle complete ───")


async def main() -> None:
    logger.info("Network Bot initialising…")
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
        id="network_cycle",
        name="Network Cycle",
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