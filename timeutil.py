"""Philippine time (DB_TIME_ZONE, default +08:00) regardless of the server's time zone."""
import os
from datetime import datetime, timedelta, timezone


def _offset(text):
    sign = -1 if text.strip().startswith("-") else 1
    hours, _, minutes = text.strip().lstrip("+-").partition(":")
    return timezone(sign * timedelta(hours=int(hours or 0), minutes=int(minutes or 0)))


LOCAL_TZ = _offset(os.environ.get("DB_TIME_ZONE", "+08:00"))


def now_local():
    """Current PH time as a naive datetime."""
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)


def today_local():
    """Current PH date."""
    return now_local().date()
