"""The study's data model. One definition, portable to SQLite and PostgreSQL."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass



class Study(Base):
    """One evaluation run: `dashboard_pilot_v1`, later a distinct main-study id."""
    __tablename__ = "studies"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
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
    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), index=True)
    paper_key: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(400))
    submission_pdf_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"), nullable=True)
    submission_text_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"), nullable=True)
    is_training_only: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("study_id", "paper_key", name="uq_paper_study_key"),)


class Asset(Base):
    """One frozen file: a PDF, a rendered-markdown text blob, or a JSON quote index."""
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    storage_backend: Mapped[str] = mapped_column(String(20), default="local")
    storage_key: Mapped[str] = mapped_column(String(400))
    sha256: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String(100))
    source_path: Mapped[str | None] = mapped_column(String(600), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Report(Base):
    """One system's frozen output for one paper. `system_id` is never sent to a participant (see api schemas) -- only used server-side for canonical ordering, the admin export, and E1/E2 analysis."""
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), index=True)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id"), index=True)
    system_id: Mapped[str] = mapped_column(String(40))
    view_type: Mapped[str] = mapped_column(String(20))
    content_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"))
    quote_index_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"), nullable=True)
    content_version: Mapped[str] = mapped_column(String(120))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("paper_id", "system_id", name="uq_report_paper_system"),)



class Task(Base):
    """A canonical (paper, unordered system pair) to be judged -- NOT rater-specific."""
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), index=True)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id"), index=True)
    system_a: Mapped[str] = mapped_column(String(40))
    system_b: Mapped[str] = mapped_column(String(40))
    report_a_id: Mapped[str] = mapped_column(ForeignKey("reports.id"))
    report_b_id: Mapped[str] = mapped_column(ForeignKey("reports.id"))
    pair_key: Mapped[str] = mapped_column(String(160))
    is_practice: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("study_id", "pair_key", name="uq_task_pair"),)


class Participant(Base):
    """A pseudonymous rater or an admin. `code_display` (e.g. "R01") is shown back to the person at code-creation time only; the login secret is never stored, only its HMAC (see security.py) -- the same property a password hash gives a login password, applied to an access code instead of a password."""
    __tablename__ = "participants"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), index=True)
    code_display: Mapped[str] = mapped_column(String(40))
    code_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="participant")
    ordinal: Mapped[int] = mapped_column(Integer)
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
    """One task, handed to one participant, with THIS participant's A/B orientation."""
    __tablename__ = "assignments"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    orientation: Mapped[str] = mapped_column(String(10))
    order_index: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="not_started")
    is_practice: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active_ms: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    draft: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("study_id", "task_id", "participant_id", name="uq_assignment_once"),)


class FinalResponse(Base):
    """The finalised (submitted) answer for one Assignment. Created exactly once, in the same transaction as Assignment.status -> "submitted" (see routers/participant.py's `submit_task`). Never mutated by a participant afterward; an admin correction (rare) writes a new row version and an AuditEvent, never edits this one in place."""
    __tablename__ = "final_responses"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id"), index=True, unique=True)
    criteria: Mapped[dict] = mapped_column(JSON)
    receipt_id: Mapped[str] = mapped_column(String(64), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    revision: Mapped[int] = mapped_column(Integer)
    superseded_by_correction: Mapped[bool] = mapped_column(Boolean, default=False)


class PaperFamiliarity(Base):
    """Asked once per (participant, paper) -- the first task opened for that paper."""
    __tablename__ = "paper_familiarity"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), index=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id"), index=True)
    familiarity: Mapped[str] = mapped_column(String(20))
    read_before: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("participant_id", "paper_id", name="uq_familiarity_once"),)


class PaperReading(Base):
    """The per-paper reading step of a non-pilot study: before any task of a paper opens, the participant reads (or skims) the plain submission and confirms it. One row per (participant, paper). `opened_at` is the first visit to the reading page, `confirmed_at` the confirmation that unlocks the paper's tasks, `active_ms` the time the page was visible and focused as measured in the browser -- recorded, never used to block anyone."""
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
    """A server-tracked login session. The cookie carries only an opaque token; this row (looked up by the token's hash) is the actual authority, so admin revocation and the 7-day cap are enforced here, not by trusting whatever the cookie says."""
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
    actor: Mapped[str] = mapped_column(String(80))
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
