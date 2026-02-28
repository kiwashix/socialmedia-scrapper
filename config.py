"""
config.py – Loads and exposes all bot settings from environment / .env file.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID: int = int(os.environ["TELEGRAM_CHAT_ID"])

#─── Reddit Settings ────────────────────────────────────────────
REDDIT_MIN_SCORE: int = int(os.environ["REDDIT_MIN_SCORE"])

# ── Groq ─────────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.environ["GROQ_API_KEY"]

# ── Scheduler ─────────────────────────────────────────────────────────────────
POLL_INTERVAL_MINUTES: int = int(os.getenv("POLL_INTERVAL_MINUTES", "30"))

# ── Misc ──────────────────────────────────────────────────────────────────────
MAX_ITEMS_PER_RUN: int = int(os.getenv("MAX_ITEMS_PER_RUN", "5"))
SUMMARY_LANGUAGE: str = os.getenv("SUMMARY_LANGUAGE", "English")
DB_PATH: str = os.getenv("DB_PATH", "marathon_bot.db")
