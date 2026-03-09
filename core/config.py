"""
config.py – Loads and exposes all bot settings from environment / .env file.
"""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID: int = int(os.environ["TELEGRAM_CHAT_ID"])

#─── Reddit Settings ────────────────────────────────────────────
REDDIT_MIN_SCORE: int = int(os.environ["REDDIT_MIN_SCORE"])

# ── Groq ─────────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.environ["GROQ_API_KEY"]
SCITELY_API_KEY: str = os.environ["SCITELY_API_KEY"]

# ── Scheduler ─────────────────────────────────────────────────────────────────
POLL_INTERVAL_MINUTES: int = int(os.getenv("POLL_INTERVAL_MINUTES", "30"))

# ── Misc ──────────────────────────────────────────────────────────────────────
MAX_ITEMS_PER_RUN: int = int(os.getenv("MAX_ITEMS_PER_RUN", "5"))
MAX_PER_SOURCE: int = int(os.getenv("MAX_PER_SOURCE", "10"))
MAX_AGE_DAYS: int = int(os.getenv("MAX_AGE_DAYS", "3"))  # Отбрасывать новости старше N дней
SUMMARY_LANGUAGE: str = os.getenv("SUMMARY_LANGUAGE", "English")
DB_PATH: str = os.getenv("DB_PATH", "network_bot.db")

SOURCES_DIR = Path("sources")

GAMES = ["valorant", "cs2", "pubg", "marathon"]
SOURCES_YAML: dict[str, dict] = {}

for game in GAMES:
    path = SOURCES_DIR / f"{game}.yaml"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            SOURCES_YAML[game] = yaml.safe_load(f)
    else:
        SOURCES_YAML[game] = {"sources": {}}

# ─────────── Хранение последней даты обработки для источников ───────────
# Словарь: game -> source_key -> datetime последней обработанной новости
LAST_PROCESSED_DATE: dict[str, dict[str, datetime]] = {}

for game, data in SOURCES_YAML.items():
    LAST_PROCESSED_DATE[game] = {}
    for source_type, sources in data.get("sources", {}).items():
        for i, source in enumerate(sources):
            # source_key уникально идентифицируется как <type>:<id или индекс>
            key = f"{source_type}:{source.get('id', str(i))}"
            LAST_PROCESSED_DATE[game][key] = datetime(1970, 1, 1, tzinfo=timezone.utc)