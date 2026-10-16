"""The system's clock: Philippine time (DB_TIME_ZONE, default +08:00) whatever
time zone the computer or hosting server runs in, so the dates and times the
app shows, checks and stores always agree with the database (which uses the
same offset for NOW() and CURRENT_TIMESTAMP)."""
import os
from datetime import datetime, timedelta, timezone


def _offset(text):
    sign = -1 if text.strip().startswith("-") else 1
    hours, _, minutes = text.strip().lstrip("+-").partition(":")
    return timezone(sign * timedelta(hours=int(hours or 0), minutes=int(minutes or 0)))


LOCAL_TZ = _offset(os.environ.get("DB_TIME_ZONE", "+08:00"))


def now_local():
    """Current local (Philippine) date and time, as a naive datetime like the database's."""
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)


def today_local():
    """Current local (Philippine) date."""
    return now_local().date()
