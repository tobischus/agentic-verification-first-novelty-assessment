"""Live end-to-end HTTP tests against a RUNNING server (`cli.py serve`).

These are deliberately not TestClient tests: they drive the same URLs, cookies, CSRF
header and asset streaming a browser does, against the real ASGI server and the real
SQLite database, so what passes here is what a participant's browser will actually get.
The pure-unit checks live in tests/test_e2_stats.py; the in-process API checks that need
a throwaway database live in tests/test_api_security.py.

Run (server must already be up on 127.0.0.1:8010):
    python -m pytest final_evaluation/tests/test_flow_live.py -v

Skipped automatically when no server is listening, so a plain `pytest` run of the whole
directory does not fail on a machine where the dashboard is not running.
"""
from __future__ import annotations

import csv
import io
import json
import os
import zipfile
from pathlib import Path

import httpx
import pytest

BASE = os.getenv("FE_TEST_BASE", "http://127.0.0.1:8010")
FE_ROOT = Path(__file__).resolve().parents[1]
CRITERIA = ("submission_fidelity", "comparison_specificity", "presented_evidence",
           "conclusion_warrant", "reviewer_usefulness")


def _server_up() -> bool:
    try:
        return httpx.get(f"{BASE}/api/health", timeout=3.0).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _server_up(), reason=f"no study server listening at {BASE}")


# These tests WRITE responses, so they must never point at the real study database.
# FE_TEST_DB_TAG selects which database's credential files to use; the default,
# `test_study`, is the throwaway database created by:
#   DATABASE_URL=sqlite:///final_evaluation/private/test_study.sqlite \
#     python -m final_evaluation.cli init-db && ... seed-pilot && ... create-participants
# and served by a server started with the same DATABASE_URL. Running against
# `local_study` would put test answers in the pilot's own data -- see README.md.
DB_TAG = os.getenv("FE_TEST_DB_TAG", "test_study")
STUDY = os.getenv("FE_TEST_STUDY", "dashboard_pilot_v1")


def _codes() -> dict:
    """Participant codes from the local private file -- never printed by these tests."""
    path = FE_ROOT / "private" / f"participant_codes__{STUDY}__{DB_TAG}.csv"
    if not path.is_file():
        pytest.skip(f"no credential file for the test database: {path.name}")
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[row["code_display"]] = row["code"]
    return out


def _admin_code() -> str:
    path = FE_ROOT / "private" / f"admin_code__{STUDY}__{DB_TAG}.txt"
    if not path.is_file():
        pytest.skip(f"no admin credential file for the test database: {path.name}")
    return path.read_text(encoding="utf-8").strip()


class Client:
    """A logged-in browser-like session: cookie jar + the CSRF header the frontend sends."""

    def __init__(self, code: str):
        self.c = httpx.Client(base_url=BASE, timeout=30.0, follow_redirects=False)
        r = self.c.post("/api/auth/login", json={"code": code})
        r.raise_for_status()
        self.csrf = r.json()["csrf"]
        self.me = self.c.get("/api/me").json()

    def post(self, path, json_body):
        return self.c.post(path, json=json_body, headers={"x-fe-csrf": self.csrf})

    def get(self, path, **kw):
        return self.c.get(path, **kw)


@pytest.fixture(scope="module")
def r01():
    return Client(_codes()["R01"])


@pytest.fixture(scope="module")
def r02():
    return Client(_codes()["R02"])


def _full_criteria(winner="A"):
    return {k: {"winner": winner, "reason": f"Test reason for {k}."} for k in CRITERIA}


# --------------------------------------------------------------------------- #
# Access control
# --------------------------------------------------------------------------- #

def test_login_rejects_bad_code():
    r = httpx.post(f"{BASE}/api/auth/login", json={"code": "R01-not-the-real-secret"}, timeout=10)
    assert r.status_code == 401
    assert "invalid" in r.text.lower()


def test_unauthenticated_cannot_read_tasks_or_assets():
    assert httpx.get(f"{BASE}/api/tasks", timeout=10).status_code == 401
    assert httpx.get(f"{BASE}/api/admin/overview", timeout=10).status_code == 401
    assert httpx.get(f"{BASE}/api/admin/export", timeout=10).status_code == 401
    # An asset id that definitely exists, fetched with no session:
    assert httpx.get(f"{BASE}/api/assets/asset_doesnotexist", timeout=10).status_code == 401


def test_participant_cannot_open_another_participants_task(r01, r02):
    a2 = r02.get("/api/tasks").json()["tasks"][0]["assignment_id"]
    r = r01.get(f"/api/tasks/{a2}")
    # R01 and R02 share TASKS but have distinct ASSIGNMENT rows; R02's assignment id
    # must not resolve for R01 -- 404 (not 403) so the id's existence is not confirmed.
    assert r.status_code == 404


def test_participant_cannot_write_to_another_participants_task(r01, r02):
    a2 = r02.get("/api/tasks").json()["tasks"][0]["assignment_id"]
    r = r01.post(f"/api/tasks/{a2}/draft",
                 {"criteria": _full_criteria(), "expected_revision": 0,
                  "idempotency_key": "x"})
    assert r.status_code == 404


def test_csrf_required_for_mutations(r01):
    a = r01.get("/api/tasks").json()["tasks"][0]["assignment_id"]
    # Same cookies, no CSRF header -> rejected.
    r = r01.c.post(f"/api/tasks/{a}/draft",
                   json={"criteria": {}, "expected_revision": 0, "idempotency_key": "x"})
    assert r.status_code == 403


def test_participant_is_not_admin(r01):
    assert r01.get("/api/admin/overview").status_code == 403
    assert r01.get("/api/admin/export").status_code == 403


# --------------------------------------------------------------------------- #
# Assets: submission + reports reachable, prior-work never present at all
# --------------------------------------------------------------------------- #

def test_submission_and_report_assets_load_for_own_task(r01):
    t = r01.get("/api/tasks").json()["tasks"][0]
    detail = r01.get(f"/api/tasks/{t['assignment_id']}").json()
    sub_id = detail["paper"]["submission_pdf_asset_id"]
    r = r01.get(f"/api/assets/{sub_id}")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    for side in ("report_a", "report_b"):
        rep = detail[side]
        rr = r01.get(f"/api/assets/{rep['content_asset_id']}")
        assert rr.status_code == 200 and len(rr.content) > 500


def test_task_detail_never_reveals_system_identity(r01):
    t = r01.get("/api/tasks").json()["tasks"][0]
    body = r01.get(f"/api/tasks/{t['assignment_id']}").text.lower()
    for system in ("agent", "linear", "opennovelty", "deepreviewer", "afzal"):
        assert f'"system_id": "{system}"' not in body
        assert f'"{system}"' not in body.replace('"paper_title"', "")


def test_no_prior_work_pdf_asset_exists_in_this_study():
    """The E2 boundary is structural: no prior-work PDF is ever imported, so there is no
    asset id that could be served. Checked against the database itself, not the API."""
    import sys
    sys.path.insert(0, str(FE_ROOT.parent))
    from final_evaluation.dashboard.backend import db as db_mod, models
    from final_evaluation.dashboard.backend.settings import get_settings
    s = get_settings()
    Session = db_mod.make_session_factory(db_mod.make_engine(s.database_url))
    db = Session()
    try:
        pdfs = db.query(models.Asset).filter(models.Asset.kind == "pdf").all()
        # Every PDF asset must be either a submission or a report (opennovelty native).
        paper_pdf_ids = {p.submission_pdf_asset_id for p in db.query(models.Paper)}
        report_asset_ids = {r.content_asset_id for r in db.query(models.Report)}
        for a in pdfs:
            assert a.id in paper_pdf_ids or a.id in report_asset_ids, (
                f"unexpected PDF asset {a.id} ({a.source_path}) -- prior-work PDFs must "
                "never be imported into a study database")
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Autosave, revisions, submit
# --------------------------------------------------------------------------- #

def _fresh_task(client) -> str:
    for t in client.get("/api/tasks").json()["tasks"]:
        if t["status"] != "submitted":
            return t["assignment_id"]
    pytest.skip("no unsubmitted task left for this participant")


def test_autosave_roundtrip_and_revision_conflict(r01):
    a = _fresh_task(r01)
    detail = r01.get(f"/api/tasks/{a}").json()
    rev = detail["revision"]

    body = {"criteria": {"submission_fidelity": {"winner": "A", "reason": "First pass."}},
            "expected_revision": rev, "idempotency_key": "k1"}
    r = r01.post(f"/api/tasks/{a}/draft", body)
    assert r.status_code == 200
    new_rev = r.json()["revision"]
    assert new_rev == rev + 1

    # Re-reading gives back exactly what was saved (server is the authority).
    again = r01.get(f"/api/tasks/{a}").json()
    assert again["draft"]["submission_fidelity"]["reason"] == "First pass."
    assert again["revision"] == new_rev

    # A stale revision (simulating a second tab) must 409, not overwrite.
    stale = dict(body, expected_revision=rev, idempotency_key="k2")
    r2 = r01.post(f"/api/tasks/{a}/draft", stale)
    assert r2.status_code == 409
    payload = r2.json()
    assert payload["error"] == "revision_conflict"
    assert payload["server_revision"] == new_rev
    # The server's own copy is returned so the UI can offer both versions.
    assert payload["server_draft"]["submission_fidelity"]["reason"] == "First pass."


def test_reason_word_limit_rejected(r01):
    a = _fresh_task(r01)
    rev = r01.get(f"/api/tasks/{a}").json()["revision"]
    long_reason = " ".join(["word"] * 60)
    r = r01.post(f"/api/tasks/{a}/draft", {
        "criteria": {"submission_fidelity": {"winner": "A", "reason": long_reason}},
        "expected_revision": rev, "idempotency_key": "k3"})
    assert r.status_code == 422


def test_submit_requires_familiarity_then_succeeds_and_is_idempotent(r01):
    a = _fresh_task(r01)
    detail = r01.get(f"/api/tasks/{a}").json()
    rev = detail["revision"]
    crit = _full_criteria("A")

    r = r01.post(f"/api/tasks/{a}/draft",
                 {"criteria": crit, "expected_revision": rev, "idempotency_key": "s0"})
    rev = r.json()["revision"]

    if detail["familiarity"] is None:
        # Submitting before the per-paper questions are answered must fail.
        r_early = r01.post(f"/api/tasks/{a}/submit",
                           {"criteria": crit, "expected_revision": rev, "idempotency_key": "s1"})
        assert r_early.status_code == 422
        ok = r01.post("/api/familiarity", {"paper_id": detail["paper"]["paper_id"],
                                           "familiarity": "moderate", "read_before": False})
        assert ok.status_code == 200

    r1 = r01.post(f"/api/tasks/{a}/submit",
                  {"criteria": crit, "expected_revision": rev, "idempotency_key": "s1"})
    assert r1.status_code == 200, r1.text
    receipt = r1.json()["receipt_id"]
    assert receipt.startswith("RCPT-")

    # Same idempotency key again (double click / retry) -> same receipt, still one response.
    r2 = r01.post(f"/api/tasks/{a}/submit",
                  {"criteria": crit, "expected_revision": rev, "idempotency_key": "s1"})
    assert r2.status_code == 200
    assert r2.json()["receipt_id"] == receipt
    assert r2.json()["already_final"] is True

    # A DIFFERENT key on an already-final task is a conflict, not a second submission.
    r3 = r01.post(f"/api/tasks/{a}/submit",
                  {"criteria": crit, "expected_revision": rev, "idempotency_key": "other"})
    assert r3.status_code == 409

    # Finalised tasks are read-only for drafts too.
    r4 = r01.post(f"/api/tasks/{a}/draft",
                  {"criteria": crit, "expected_revision": rev + 1, "idempotency_key": "d9"})
    assert r4.status_code == 409

    after = r01.get(f"/api/tasks/{a}").json()
    assert after["status"] == "submitted"
    assert after["final"]["receipt_id"] == receipt


def test_ab_orientation_is_stable_across_reads_and_opposite_between_raters(r01, r02):
    t1 = {t["assignment_id"]: t for t in r01.get("/api/tasks").json()["tasks"]}
    first = list(t1)[0]
    d1 = r01.get(f"/api/tasks/{first}").json()
    d1_again = r01.get(f"/api/tasks/{first}").json()
    assert d1["report_a"]["report_ref"] == d1_again["report_a"]["report_ref"]

    # Find R02's assignment for the SAME underlying task by matching the report pair.
    pair1 = {d1["report_a"]["report_ref"], d1["report_b"]["report_ref"]}
    for t in r02.get("/api/tasks").json()["tasks"]:
        d2 = r02.get(f"/api/tasks/{t['assignment_id']}").json()
        if {d2["report_a"]["report_ref"], d2["report_b"]["report_ref"]} == pair1:
            assert d2["report_a"]["report_ref"] == d1["report_b"]["report_ref"], (
                "R01 and R02 must see the same pair in opposite order")
            return
    pytest.fail("no matching task found for R02")


# --------------------------------------------------------------------------- #
# Admin export
# --------------------------------------------------------------------------- #

def test_admin_export_contains_everything_and_no_secrets():
    admin = Client(_admin_code())
    r = admin.get("/api/admin/export")
    assert r.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(z.namelist())
    for expected in ("ratings.jsonl", "ratings_long.csv", "assignments.csv", "tasks.json",
                    "manifest.json", "rubric.txt", "protocol.md", "technical_issues.csv",
                    "completion.csv"):
        assert expected in names, f"missing {expected} in export"

    blob = b"".join(z.read(n) for n in names).decode("utf-8", errors="ignore")
    codes = _codes()
    for code in codes.values():
        assert code not in blob, "a raw access code leaked into the research export"
    assert _admin_code() not in blob
    assert "code_hash" not in blob and "token_hash" not in blob

    # A/B is resolved back to real system ids for analysis.
    rows = [json.loads(ln) for ln in z.read("ratings.jsonl").decode("utf-8").splitlines() if ln.strip()]
    assert rows, "export has no rating rows"
    for row in rows:
        assert row["system_a"] in ("agent", "linear", "opennovelty", "deepreviewer", "afzal")
        assert row["orientation"] in ("forward", "reversed")
