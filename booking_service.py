from datetime import datetime
import math


def parse_iso(dt_str: str):
    """Parse ISO date or datetime string to datetime object; return None if invalid."""
    if not dt_str:
        return None
    try:
        # support YYYY-MM-DD or full ISO
        if 'T' in dt_str:
            return datetime.fromisoformat(dt_str)
        return datetime.fromisoformat(dt_str + 'T00:00:00')
    except Exception:
        return None


def compute_total_hours(start_iso: str, end_iso: str) -> int:
    start = parse_iso(start_iso)
    end = parse_iso(end_iso)
    if not start or not end or end <= start:
        return 0
    diff = end - start
    hours = math.ceil(diff.total_seconds() / 3600)
    return int(hours)


def breakdown_days_hours(total_hours: int):
    days = total_hours // 24
    rem = total_hours % 24
    return days, rem


def compute_price(total_hours: int, per_day_price: float) -> dict:
    """Return price breakdown and total.

    Returns: { 'days': int, 'hours': int, 'price_days': float, 'price_hours': float, 'total': float }
    """
    per_hour = per_day_price / 24.0
    days, rem = breakdown_days_hours(total_hours)
    if total_hours >= 24:
        price_days = days * per_day_price
        price_hours = rem * per_hour
    else:
        price_days = 0.0
        price_hours = total_hours * per_hour
    total = price_days + price_hours
    return {
        'days': days,
        'hours': rem,
        'price_days': round(price_days, 2),
        'price_hours': round(price_hours, 2),
        'total': round(total, 2),
    }
