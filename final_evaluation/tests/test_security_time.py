"""Stored timestamps must compare correctly on both databases this study can run on.

SQLite returns a `DateTime(timezone=True)` column NAIVE; PostgreSQL returns it aware. Any
code that compares such a value against `datetime.now(timezone.utc)` without normalising
works on one and raises `TypeError` on the other -- and a TypeError inside a request
handler is a 500, not a refusal.

That is not hypothetical: `security.is_locked` did exactly this. On SQLite, once a
participant had been locked out after failed logins, EVERY later login attempt crashed
with 500 instead of being refused, and the participant could not get back in even after
the lockout had expired. Found while running the live flow tests on 2026-09-18.

    python -m pytest final_evaluation/tests/test_security_time.py
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

FE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FE_ROOT / "dashboard"))

from backend import security  # noqa: E402


def test_is_locked_accepts_a_naive_timestamp_as_utc():
    """What SQLite hands back: no offset, written by lockout_after_failure() in UTC."""
    naive_future = datetime.utcnow() + timedelta(minutes=5)
    naive_past = datetime.utcnow() - timedelta(minutes=5)
    assert security.is_locked(naive_future) is True
    assert security.is_locked(naive_past) is False


def test_is_locked_accepts_an_aware_timestamp():
    """What PostgreSQL hands back."""
    assert security.is_locked(datetime.now(timezone.utc) + timedelta(minutes=5)) is True
    assert security.is_locked(datetime.now(timezone.utc) - timedelta(minutes=5)) is False


def test_is_locked_without_a_lockout():
    assert security.is_locked(None) is False


def test_lockout_is_written_aware_and_reads_back_as_locked():
    """The value the code stores must satisfy its own predicate, in either shape."""
    until = security.lockout_after_failure(security.MAX_FAILED_LOGINS - 1)
    assert until is not None and until.tzinfo is not None
    assert security.is_locked(until) is True
    # ... and still, after a round trip through a driver that drops the offset.
    assert security.is_locked(until.replace(tzinfo=None)) is True
    assert security.lockout_after_failure(0) is None
