"""The study's data model. One definition, portable to SQLite and PostgreSQL.

Every table uses plain, dialect-neutral SQLAlchemy types (`String`, `Integer`, `Boolean`,
`JSON`, `DateTime`) -- no PostgreSQL-only ENUM, no SQLite-only affinity trick. `JSON`
compiles to a native `jsonb` column on PostgreSQL and to `TEXT` with transparent
(de)serialisation on SQLite; the ORM code never has to know which.

IDs are opaque strings (`uuid4().hex`), not autoincrement integers: a participant
manipulating `assignment_id=7` to `8` should not even land on a plausible neighbour, and
opaque IDs generate identically in either database without touching a sequence.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------- #
# Study, papers, reports, assets
# --------------------------------------------------------------------------- #

class Study(Base):
    """One evaluation run: `dashboard_pilot_v1`, later a distinct main-study id.

    `status`: draft (being seeded, not shown to participants) | active (accepting
    responses) | closed (read-only; admin can still export). Papers, tasks and
    assignments all key off `study_id`, so `dashboard_pilot_v1` and any later main-study
    id never share a row -- satisfying "Hauptstudie bekommt eine neue ID und keine
    Pilotantworten" by construction rather than by a filter someone has to remember.
    """
    __tablename__ = "studies"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g. "dashboard_pilot_v1"
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    is_pilot: Mapped[bool] = mapped_column(Boolean, default=True)
    contact_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rubric_version: Mapped[str] = mapped_column(String(64), default="novelty_report_judge_v3")
    instructions_version: Mapped[str] = mapped_column(String(64), default="human_instructions_v2")
    ui_version: Mapped[str] = mapped_column(String(64), default="dashboard_v1")
    assignment_seed: Mapped[int] = mapped_column(Integer, default=43)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Paper(Base):
    __tablename__ = "papers"
    id: Mapped[str] = mapped_column(String(160), primary_key=True)  # f"{study_id}::{paper_key}"
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), index=True)
    paper_key: Mapped[str] = mapped_column(String(80))  # e.g. "graphrag_when_to_use"
    title: Mapped[str] = mapped_column(String(400))
    submission_pdf_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"), nullable=True)
    submission_text_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"), nullable=True)
    is_training_only: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("study_id", "paper_key", name="uq_paper_study_key"),)


class Asset(Base):
    """One frozen file: a PDF, a rendered-markdown text blob, or a JSON quote index.

    `storage_backend` + `storage_key` are the only backend-specific fields in the whole
    schema, and even those are just a tag and a path/key string -- `storage.py` is where
    "local" resolves to a file under LOCAL_ASSET_ROOT and "supabase" resolves to a signed
    URL from the private bucket. Nothing else in the model or the API branches on backend.
    """
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # pdf | markdown | json | image
    storage_backend: Mapped[str] = mapped_column(String(20), default="local")
    storage_key: Mapped[str] = mapped_column(String(400))
    sha256: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String(100))
    source_path: Mapped[str | None] = mapped_column(String(600), nullable=True)  # provenance only
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Report(Base):
    """One system's frozen output for one paper. `system_id` is never sent to a
    participant (see api schemas) -- only used server-side for canonical ordering,
    the admin export, and E1/E2 analysis."""
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(160), primary_key=True)  # f"{paper_id}::{system_id}" -- 64 was too short (PostgreSQL enforces it, SQLite does not)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), index=True)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id"), index=True)
    system_id: Mapped[str] = mapped_column(String(40))  # agent|linear|opennovelty|deepreviewer|afzal
    view_type: Mapped[str] = mapped_column(String(20))  # markdown | pdf
    content_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"))
    quote_index_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"), nullable=True)
    content_version: Mapped[str] = mapped_column(String(120))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("paper_id", "system_id", name="uq_report_paper_system"),)


# --------------------------------------------------------------------------- #
# Tasks and assignments
# --------------------------------------------------------------------------- #

class Task(Base):
    """A canonical (paper, unordered system pair) to be judged -- NOT rater-specific.

    `system_a`/`system_b` are stored in a fixed canonical order (alphabetical) purely so
    `pair_key` is stable; which one a given rater actually sees as "A" is decided per
    Assignment (see below), independently for each rater.
    """
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), index=True)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id"), index=True)
    system_a: Mapped[str] = mapped_column(String(40))
    system_b: Mapped[str] = mapped_column(String(40))
    report_a_id: Mapped[str] = mapped_column(ForeignKey("reports.id"))  # canonical order's "A"
    report_b_id: Mapped[str] = mapped_column(ForeignKey("reports.id"))
    pair_key: Mapped[str] = mapped_column(String(160))  # f"{paper_key}::{system_a}::{system_b}"
    is_practice: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("study_id", "pair_key", name="uq_task_pair"),)


class Participant(Base):
    """A pseudonymous rater or an admin. `code_display` (e.g. "R01") is shown back to
    the person at code-creation time only; the login secret is never stored, only its
    HMAC (see security.py) -- the same property a password hash gives a login password,
    applied to an access code instead of a password."""
    __tablename__ = "participants"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), index=True)
    code_display: Mapped[str] = mapped_column(String(40))  # "R01" -- shown at creation, not secret
    code_hash: Mapped[str] = mapped_column(String(200))     # HMAC-SHA256(pepper, full code)
    role: Mapped[str] = mapped_column(String(20), default="participant")  # participant | admin
    ordinal: Mapped[int] = mapped_column(Integer)  # 1-based, drives orientation + order seed
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_instructions_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_experience: Mapped[str | None] = mapped_column(String(40), nullable=True)
    system_involvement: Mapped[str | None] = mapped_column(String(20), nullable=True)
    system_involvement_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("study_id", "code_display", name="uq_participant_code_display"),)


class Assignment(Base):
    """One task, handed to one participant, with THIS participant's A/B orientation.

    `order_index` is this participant's fixed position for the task in their own queue
    (seed = 100 + ordinal, frozen at seed-pilot time -- see scripts/assign.py).
    `orientation`: "forward" -> report_a/b match the Task's canonical a/b;
    "reversed" -> swapped. Never recomputed after creation (re-running seed-pilot must
    not reroll it); enforced by the unique constraint below plus assign.py checking for
    an existing row before writing.
    """
    __tablename__ = "assignments"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    orientation: Mapped[str] = mapped_column(String(10))  # forward | reversed
    order_index: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="not_started")
    is_practice: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[int] = mapped_column(Integer, default=0)  # optimistic-concurrency counter
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active_ms: Mapped[int] = mapped_column(Integer, default=0)  # accumulated, idle-gapped
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    draft: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {criteria:{...}}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("study_id", "task_id", "participant_id", name="uq_assignment_once"),)


class FinalResponse(Base):
    """The finalised (submitted) answer for one Assignment. Created exactly once, in the
    same transaction as Assignment.status -> "submitted" (see routers/participant.py's
    `submit_task`). Never mutated by a participant afterward; an admin correction (rare)
    writes a new row version and an AuditEvent, never edits this one in place."""
    __tablename__ = "final_responses"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id"), index=True, unique=True)
    criteria: Mapped[dict] = mapped_column(JSON)  # {key: {winner, reason?, unclear_reason?, locator? (pilot only)}}
    receipt_id: Mapped[str] = mapped_column(String(64), unique=True)
    # Indexed, NOT globally unique: an idempotency key is only meaningful within one
    # assignment (the replay check in submit_task compares it against THIS assignment's
    # existing row). A global unique index rejected a perfectly valid submission of a
    # DIFFERENT task that happened to reuse a key -- which a retrying client, or a test
    # harness, will do. `assignment_id` being unique is what guarantees "one final
    # response per task".
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    revision: Mapped[int] = mapped_column(Integer)  # the Assignment.revision it was submitted at
    superseded_by_correction: Mapped[bool] = mapped_column(Boolean, default=False)


class PaperFamiliarity(Base):
    """Asked once per (participant, paper) -- the first task opened for that paper."""
    __tablename__ = "paper_familiarity"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), index=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id"), index=True)
    familiarity: Mapped[str] = mapped_column(String(20))  # low | moderate | high
    read_before: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("participant_id", "paper_id", name="uq_familiarity_once"),)


class PaperReading(Base):
    """The per-paper reading step of a non-pilot study: before any task of a paper opens,
    the participant reads (or skims) the plain submission and confirms it. One row per
    (participant, paper). `opened_at` is the first visit to the reading page,
    `confirmed_at` the confirmation that unlocks the paper's tasks, `active_ms` the time
    the page was visible and focused as measured in the browser -- recorded, never used to
    block anyone."""
    __tablename__ = "paper_readings"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), index=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id"), index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active_ms: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("participant_id", "paper_id", name="uq_paper_reading_once"),)


class Session_(Base):
    """A server-tracked login session. The cookie carries only an opaque token; this row
    (looked up by the token's hash) is the actual authority, so admin revocation and the
    7-day cap are enforced here, not by trusting whatever the cookie says."""
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), index=True)
    actor: Mapped[str] = mapped_column(String(80))  # participant_id or "admin:<id>"
    event_type: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TechnicalIssue(Base):
    __tablename__ = "technical_issues"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), index=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    assignment_id: Mapped[str | None] = mapped_column(ForeignKey("assignments.id"), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
