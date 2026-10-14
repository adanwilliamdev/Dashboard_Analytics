from datetime import datetime

import pytest

from app import recurrence as rc


def test_monthly_keeps_anchor_day_across_short_months():
    d = datetime(2026, 1, 31)
    d = rc.next_occurrence(d, "monthly", 31)
    assert d == datetime(2026, 2, 28)
    d = rc.next_occurrence(d, "monthly", 31)
    assert d == datetime(2026, 3, 31)  # volta ao dia 31, nao "deriva" para 28
    assert rc.next_occurrence(datetime(2026, 12, 15), "monthly", 15) == datetime(2027, 1, 15)


def test_yearly_handles_leap_day_and_weekly():
    assert rc.next_occurrence(datetime(2024, 2, 29), "yearly", 29) == datetime(2025, 2, 28)
    assert rc.next_occurrence(datetime(2028, 2, 29), "yearly", 29) == datetime(2029, 2, 28)
    assert rc.next_occurrence(datetime(2026, 10, 9), "weekly", 9) == datetime(2026, 10, 16)
    with pytest.raises(ValueError):
        rc.next_occurrence(datetime(2026, 1, 1), "daily", 1)


def test_due_dates_backfills_up_to_today_inclusive():
    dates = rc.due_dates(datetime(2026, 8, 10), datetime(2026, 10, 10), "monthly", 10)
    assert dates == [datetime(2026, 8, 10), datetime(2026, 9, 10), datetime(2026, 10, 10)]
    assert rc.due_dates(datetime(2026, 10, 11), datetime(2026, 10, 10), "monthly", 11) == []


def test_due_dates_respects_end_date_and_limit():
    dates = rc.due_dates(datetime(2026, 10, 1), datetime(2026, 10, 30), "weekly", 1, end_date=datetime(2026, 10, 15))
    assert dates == [datetime(2026, 10, 1), datetime(2026, 10, 8), datetime(2026, 10, 15)]
    many = rc.due_dates(datetime(2000, 1, 1), datetime(2026, 1, 1), "weekly", 1, limit=5)
    assert len(many) == 5
