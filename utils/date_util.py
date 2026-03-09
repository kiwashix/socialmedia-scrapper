from datetime import datetime, timezone, timedelta


def _parse_date(date_str: str) -> datetime:
    """
    Парсит строку даты в timezone-aware datetime.
    Возвращает epoch (1970) если не удалось.
    Всегда возвращает aware datetime (UTC).
    """
    if not date_str:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)

    normalized = date_str.strip().replace("Z", "+00:00")

    # ISO-8601 (включая микросекунды и +00:00)
    try:
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass

    # Форматы без дробных секунд
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str[:len(fmt) + 6], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass

    # RFC-2822 (RSS feeds: "Mon, 02 Jan 2006 15:04:05 +0000")
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass

    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def is_recent(date_str: str, max_age_days: int) -> bool:
    """Возвращает True, если дата не старше max_age_days дней."""
    dt = _parse_date(date_str)
    if dt == datetime(1970, 1, 1, tzinfo=timezone.utc):
        return False  # Неизвестная дата — отбрасываем
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    return dt >= cutoff


def is_today(date_str: str) -> bool:
    """Возвращает True, если дата сегодняшняя."""
    dt = _parse_date(date_str)
    now = datetime.now(timezone.utc)
    return dt.date() == now.date()
