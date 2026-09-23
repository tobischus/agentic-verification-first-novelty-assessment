"""Access codes, sessions, CSRF, rate limiting, and the deterministic assignment RNG.

Nothing here is a home-grown crypto primitive: code hashing is HMAC-SHA256 (stdlib
`hmac`/`hashlib`), session tokens are `secrets.token_urlsafe`, and the "seeded RNG" for
orientation/ordering is Python's `random.Random(seed)` -- deterministic and reproducible,
which is the actual requirement (a fixed, auditable assignment), not cryptographic
unpredictability.
"""
from __future__ import annotations

import hashlib
import hmac
import random
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

SESSION_TTL_PARTICIPANT = timedelta(days=7)
SESSION_TTL_ADMIN = timedelta(days=7)

# --------------------------------------------------------------------------- #
# Access codes: "R01-<32 hex chars>" = 128 bits of entropy in the secret half.
# The full code is the login credential; only its HMAC is ever stored.
# --------------------------------------------------------------------------- #

def generate_code(display: str) -> str:
    secret = secrets.token_hex(16)  # 128 bits
    return f"{display}-{secret}"


def hash_code(full_code: str, pepper: str) -> str:
    if not pepper:
        raise RuntimeError("ACCESS_CODE_PEPPER is not set -- refusing to hash a code with no pepper")
    return hmac.new(pepper.encode("utf-8"), full_code.strip().encode("utf-8"),
                    hashlib.sha256).hexdigest()


def codes_match(full_code: str, stored_hash: str, pepper: str) -> bool:
    return hmac.compare_digest(hash_code(full_code, pepper), stored_hash)


# --------------------------------------------------------------------------- #
# Sessions
# --------------------------------------------------------------------------- #

def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    # No pepper needed here: the token itself already has 256 bits of entropy and is
    # never reused/guessable the way a human-chosen password would be. Hashing still
    # means a DB read (backup, leaked export) cannot be replayed as a live cookie.
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


# --------------------------------------------------------------------------- #
# Rate limiting for login attempts -- in-process, per-participant lockout.
#
# A Render free instance runs a single worker, so an in-memory counter genuinely limits
# attempts against a given code; it resets on a cold restart, which only ever makes the
# limit MORE permissive, never less. A multi-instance deployment would need a shared
# store (e.g. the same Postgres) instead -- noted here rather than silently assumed away.
# --------------------------------------------------------------------------- #

MAX_FAILED_LOGINS = 8
LOCKOUT = timedelta(minutes=15)


def is_locked(locked_until: datetime | None) -> bool:
    """Whether the lockout is still running.

    SQLite gives the value back NAIVE even though the column is DateTime(timezone=True);
    PostgreSQL keeps the offset. Comparing a naive value against an aware `now` raises
    TypeError, which FastAPI turns into a 500 -- so on SQLite, every login attempt after
    a first lockout crashed instead of being refused, and the participant could never get
    back in even after the 15 minutes had passed. A naive value was written by
    lockout_after_failure() in UTC, so it is read as UTC. Same normalisation as
    deps.py's session-expiry check.
    """
    if not locked_until:
        return False
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    return locked_until > datetime.now(timezone.utc)


def lockout_after_failure(failed_logins: int) -> datetime | None:
    if failed_logins + 1 >= MAX_FAILED_LOGINS:
        return datetime.now(timezone.utc) + LOCKOUT
    return None


# A second layer: a small global token bucket per source IP, independent of which code
# was tried, so a scan across many guessed display-ids cannot bypass the per-code lock.
_ip_attempts: dict[str, list[float]] = {}
IP_WINDOW_S = 60.0
IP_MAX_ATTEMPTS = 20


def ip_rate_limited(ip: str) -> bool:
    now = time.monotonic()
    hist = [t for t in _ip_attempts.get(ip, []) if now - t < IP_WINDOW_S]
    hist.append(now)
    _ip_attempts[ip] = hist
    return len(hist) > IP_MAX_ATTEMPTS


# --------------------------------------------------------------------------- #
# Deterministic assignment: orientation + ordering. Pure functions of (seed, key) --
# same inputs always produce the same output, in either process, forever. Used once at
# seed-pilot time and then FROZEN into the Assignment row; never recomputed on read.
# --------------------------------------------------------------------------- #

def orientation_bit(seed: int, pair_key: str) -> int:
    """A fixed 0/1 per (seed, pair_key), independent of any participant."""
    rng = random.Random(f"{seed}:orientation:{pair_key}")
    return rng.randint(0, 1)


def orientation_for(seed: int, pair_key: str, participant_ordinal: int) -> str:
    """Guarantees two participants with ordinals of different parity (e.g. R01, R02)
    always see a given pair in OPPOSITE orientation -- the pilot's explicit requirement.
    For >2 raters this still varies per task while keeping that same guarantee for any
    even/odd pair of raters."""
    bit = orientation_bit(seed, pair_key) ^ (participant_ordinal % 2)
    return "reversed" if bit else "forward"


def block_and_task_order(order_seed: int, paper_keys: list[str],
                         tasks_by_paper: dict[str, list[str]]) -> list[str]:
    """Shuffle paper blocks, then shuffle tasks within each block, both with
    `order_seed` (= 100 + participant ordinal). Returns a flat list of task ids in the
    order this participant will see them. Deterministic and re-derivable, but callers
    should still persist `order_index` on Assignment rather than recomputing on every
    request -- the point is auditability, not recomputation cost."""
    rng = random.Random(order_seed)
    papers = list(paper_keys)
    rng.shuffle(papers)
    out: list[str] = []
    for p in papers:
        ids = list(tasks_by_paper.get(p, []))
        rng.shuffle(ids)
        out.extend(ids)
    return out


# --------------------------------------------------------------------------- #
# Receipts / idempotency
# --------------------------------------------------------------------------- #

def new_receipt_id() -> str:
    return "RCPT-" + secrets.token_hex(8).upper()


@dataclass
class RateLimitResult:
    allowed: bool
    retry_after_s: float = 0.0
