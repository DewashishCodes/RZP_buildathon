from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.detection.receivables import classify_receivable

NOW = datetime(2026, 8, 23, tzinfo=timezone.utc)


def make_case(days_overdue: int, disputed: bool = False):
    return SimpleNamespace(due_at=NOW - timedelta(days=days_overdue), disputed=disputed)


def test_disputed_overrides_bucket_regardless_of_days_overdue():
    assert classify_receivable(make_case(0, disputed=True), now=NOW) == "disputed"
    assert classify_receivable(make_case(90, disputed=True), now=NOW) == "disputed"


def test_zero_days_overdue_is_early():
    assert classify_receivable(make_case(0), now=NOW) == "overdue_early"


def test_boundary_at_15_days_is_early():
    assert classify_receivable(make_case(15), now=NOW) == "overdue_early"


def test_16_days_overdue_is_mid():
    assert classify_receivable(make_case(16), now=NOW) == "overdue_mid"


def test_boundary_at_45_days_is_mid():
    assert classify_receivable(make_case(45), now=NOW) == "overdue_mid"


def test_46_days_overdue_is_late():
    assert classify_receivable(make_case(46), now=NOW) == "overdue_late"


def test_far_overdue_is_late():
    assert classify_receivable(make_case(200), now=NOW) == "overdue_late"


def test_naive_due_at_is_treated_as_utc():
    naive_case = SimpleNamespace(due_at=(NOW - timedelta(days=5)).replace(tzinfo=None), disputed=False)
    assert classify_receivable(naive_case, now=NOW) == "overdue_early"


def test_missing_due_at_fails_safe_to_overdue_late():
    malformed_case = SimpleNamespace(due_at=None, disputed=False)
    assert classify_receivable(malformed_case, now=NOW) == "overdue_late"
