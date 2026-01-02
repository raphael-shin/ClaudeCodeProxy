import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[1]
sys.path.append(str(root))

from src.proxy.usage import _get_bucket_start


# Feature: cost-visibility, Property 10: KST Bucket Boundaries

def test_week_bucket_starts_on_sunday_kst() -> None:
    kst = ZoneInfo("Asia/Seoul")
    ts = datetime(2025, 1, 6, 12, 30, tzinfo=kst)  # Monday

    bucket_start = _get_bucket_start(ts, "week", tz=kst)

    assert bucket_start == datetime(2025, 1, 5, 0, 0, tzinfo=kst)


def test_week_bucket_same_day_on_sunday_kst() -> None:
    kst = ZoneInfo("Asia/Seoul")
    ts = datetime(2025, 1, 5, 23, 59, tzinfo=kst)  # Sunday

    bucket_start = _get_bucket_start(ts, "week", tz=kst)

    assert bucket_start == datetime(2025, 1, 5, 0, 0, tzinfo=kst)


def test_day_bucket_kst_midday() -> None:
    kst = ZoneInfo("Asia/Seoul")
    ts = datetime(2025, 2, 10, 14, 5, tzinfo=kst)

    bucket_start = _get_bucket_start(ts, "day", tz=kst)

    assert bucket_start == datetime(2025, 2, 10, 0, 0, tzinfo=kst)
