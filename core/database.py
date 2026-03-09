"""
database.py – SQLite store для дедупликации новостей.

ИЗМЕНЕНИЯ:
  - Добавлена колонка published_at (дата публикации новости)
  - Добавлена миграция для существующих БД (ALTER TABLE IF NOT EXISTS)
  - mark_processed теперь принимает published параметр
"""
import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime
from core.config import DB_PATH

logger = logging.getLogger(__name__)


@contextmanager
def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they don't exist yet. Applies migrations for existing DBs."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_items (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                source       TEXT    NOT NULL,
                item_id      TEXT    NOT NULL,
                url          TEXT,
                title        TEXT,
                published_at TEXT,           -- дата публикации новости
                processed_at TEXT    NOT NULL, -- когда бот обработал
                UNIQUE(source, item_id)
            )
        """)
        # Миграция для существующих БД без колонки published_at
        try:
            conn.execute("ALTER TABLE processed_items ADD COLUMN published_at TEXT")
            logger.info("Migration: added published_at column")
        except Exception:
            pass  # колонка уже есть — норм
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_item
            ON processed_items(source, item_id)
        """)
    logger.info("Database initialised at %s", DB_PATH)


def is_processed(source: str, item_id: str) -> bool:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_items WHERE source=? AND item_id=?",
            (source, item_id)
        ).fetchone()
    return row is not None


def mark_processed(
    source: str,
    item_id: str,
    url: str = "",
    title: str = "",
    published: str = "",  # ✅ новый параметр
) -> None:
    """Record that a news item has been processed."""
    with _get_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO processed_items
               (source, item_id, url, title, published_at, processed_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source, item_id, url, title, published, datetime.utcnow().isoformat())
        )


def get_stats() -> dict:
    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM processed_items").fetchone()[0]
        by_source = conn.execute(
            "SELECT source, COUNT(*) as cnt FROM processed_items GROUP BY source"
        ).fetchall()
    return {"total": total, "by_source": {r["source"]: r["cnt"] for r in by_source}}