"""Real-browser walkthrough of the participant flow.

Not a pytest module on purpose: it needs a running server AND a browser, and it WRITES a
submitted response, so it is run deliberately rather than as part of `pytest`. The
pytest suite covers the same guarantees over HTTP (tests/test_flow_live.py); this adds
what only a browser can answer -- does the page actually render, do the quote marks match
the stored verbatim status, does a reload come back to the task being rated.

What it checks:
  1. instructions show the current (v2) wording;
  2. background questions asked once per paper, carried over to the next task on it;
  3. quote ✓ appears only where a stored verbatim check matched, with PDF navigation as
     its own separate control;
  4. contents navigation, collapsible per-source comparisons, deferred form errors;
  5. autosave, reload-and-resume, submit.

Run (server up, e.g. `python -m final_evaluation.cli serve`):
    python final_evaluation/tests/browser_check.py final_evaluation/results/pilot/shots

It reads a participant code from private/participant_codes__*.csv and never prints it.
Point it at a THROWAWAY database if you do not want a real submitted response.
"""
import csv
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"
SHOT = Path(sys.argv[1] if len(sys.argv) > 1 else "shots")
SHOT.mkdir(parents=True, exist_ok=True)
CODES = Path("final_evaluation/private/participant_codes__dashboard_pilot_v1__local_study.csv")

code = None
with open(CODES, encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        if row["code_display"] == "R02":
            code = row["code"]
print("using participant R02")

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


with sync_playwright() as p:
    # Playwright's own chromium build is not downloaded on this machine; the
    # system Chrome is used instead (same engine, real browser).
    browser = p.chromium.launch(channel="chrome")
    ctx = browser.new_context(viewport={"width": 1366, "height": 768})
    page = ctx.new_page()
    page.on("pageerror", lambda e: check("no JS page error", False, str(e)))

    # ---------- login ----------
    page.goto(BASE, wait_until="networkidle")
    page.fill("#code", code)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    page.screenshot(path=str(SHOT / "01_after_login.png"), full_page=True)

    # ---------- instructions (v2 text) ----------
    body = " ".join(page.inner_text("body").split())
    if "Before you begin" in body:
        check("instructions: new 'Do not prefer terminology' sentence",
              "Do not prefer terminology, format, length" in body)
        check("instructions: 'Verification labels are system claims' added",
              "Verification labels are system claims, not independent validation." in body)
        check("instructions: old sentence gone",
              "Do not favor matching terminology" not in body)
        page.screenshot(path=str(SHOT / "02_instructions.png"), full_page=True)
        page.check("input[type=checkbox] >> nth=0")
        page.check("input[type=checkbox] >> nth=1")
        page.select_option("select >> nth=0", "1-5")
        page.select_option("select >> nth=1", "no")
        page.locator("button:has-text('Continue')").last.click()
        page.wait_for_load_state("networkidle")

    # ---------- task list ----------
    page.wait_for_selector(".fe-task-row", timeout=15000)
    rows = page.locator(".fe-task-row")
    n_tasks = rows.count()
    check("task list shows the participant's tasks", n_tasks == 6, f"{n_tasks} rows")
    page.screenshot(path=str(SHOT / "03_task_list.png"), full_page=True)

    # Group tasks by paper heading so we can open two tasks on the SAME paper.
    groups = page.locator(".fe-paper-group")
    first_group = groups.nth(0)
    paper_title = first_group.locator("h2").inner_text()
    group_rows = first_group.locator(".fe-task-row")
    same_paper_count = group_rows.count()
    print(f"first paper group: {paper_title[:60]}... ({same_paper_count} tasks)")

    # ---------- task 1: background questions asked ----------
    group_rows.nth(0).locator("button").click()
    page.wait_for_selector(".fe-form", timeout=30000)
    page.wait_for_timeout(2500)  # let both report panels finish fetching
    body = " ".join(page.inner_text(".fe-form").split())
    check("task 1: new familiarity wording present",
          "Before starting this study, how familiar were you with this paper" in body)
    check("task 1: new read-before wording present",
          "Had you read this submission before starting this study?" in body)
    check("task 1: background questions are asked (not carried over)",
          page.locator("#fam-area").count() == 1)
    page.screenshot(path=str(SHOT / "04_task1_form.png"), full_page=True)

    # quote marks: ✓ only where a stored check exists
    verified = page.locator(".rz-quote.verified").count()
    unverified = page.locator(".rz-quote.unverified").count()
    ticks = page.locator(".rz-qmark:not(.rz-qmark-none)").count()
    dashes = page.locator(".rz-qmark-none").count()
    check("quotes: tick count equals verified-quote count",
          ticks == verified and dashes == unverified,
          f"verified={verified} unverified={unverified} ticks={ticks} dashes={dashes}")
    check("quotes: at least one verified and one unverified are visible",
          verified > 0 and unverified > 0, f"{verified}/{unverified}")
    jump_buttons = page.locator(".rz-qjump").count()
    check("quotes: PDF navigation is a separate control",
          jump_buttons > 0 and jump_buttons <= verified + unverified, f"{jump_buttons} ⤴ PDF buttons")
    # a jump button must never sit on a quote with no click target
    check("quotes: no ⤴ PDF control without a resolvable target",
          page.locator(".rz-quote:not(.qjump) .rz-qjump").count() == 0)

    # content navigation + collapsible detail comparisons
    check("report: contents navigation present", page.locator(".rr-toc").count() >= 1)
    details = page.locator(".rr-detail")
    n_details = details.count()
    open_details = page.locator(".rr-detail[open]").count()
    check("report: per-source comparisons are collapsible, collapsed by default",
          n_details > 0 and open_details == 0, f"{n_details} sections, {open_details} open")
    if n_details:
        details.nth(0).locator("summary").click()
        page.wait_for_timeout(300)
        check("report: a collapsed comparison opens with its content",
              page.locator(".rr-detail[open] .rr-detail-body").count() >= 1)

    # form errors only after interaction / submit attempt
    check("form: no validation errors before any interaction",
          page.locator(".fe-field-error").count() == 0)
    page.locator(".fe-jump-form").click()
    page.wait_for_timeout(400)
    page.locator("button:has-text('Submit')").click()
    page.wait_for_timeout(600)
    check("form: validation errors appear after a submit attempt",
          page.locator(".fe-field-error").count() > 0,
          f"{page.locator('.fe-field-error').count()} error blocks")
    page.screenshot(path=str(SHOT / "05_task1_errors_after_submit.png"), full_page=True)

    # ---------- fill in + save ----------
    page.select_option("#fam-area", "moderate")
    page.select_option("#fam-read", "false")
    keys = ["submission_fidelity", "comparison_specificity", "presented_evidence",
            "conclusion_warrant", "reviewer_usefulness"]
    for i, k in enumerate(keys):
        page.locator(f"input[name='{k}'][value='{'A' if i % 2 == 0 else 'tie'}']").check()
    boxes = page.locator(".fe-criterion textarea")
    for i in range(boxes.count()):
        boxes.nth(i).fill(f"Browser check reason {i + 1}: decisive observation recorded here.")
    page.locator(".fe-criterion textarea").nth(0).blur()
    page.wait_for_timeout(3000)
    saved_text = page.inner_text(".fe-save-state")
    check("autosave: state shows Saved", "Saved" in saved_text, saved_text.strip())
    page.screenshot(path=str(SHOT / "06_task1_filled.png"), full_page=True)

    # ---------- resume after reload ----------
    page.reload(wait_until="networkidle")
    page.wait_for_selector(".fe-form", timeout=30000)
    page.wait_for_timeout(1500)
    first_reason = page.locator(".fe-criterion textarea").nth(0).input_value()
    check("resume: draft text survived a reload",
          "Browser check reason 1" in first_reason, first_reason[:40])
    checked = page.locator("input[name='submission_fidelity']:checked").count()
    check("resume: chosen option survived a reload", checked == 1)

    # ---------- submit, then a SECOND task on the same paper ----------
    page.locator("button:has-text('Submit')").click()
    page.wait_for_timeout(2500)
    submitted_ok = "Task submitted" in page.inner_text("body")
    check("submit: confirmation page reached", submitted_ok)
    page.screenshot(path=str(SHOT / "07_submitted.png"), full_page=True)

    if submitted_ok:
        page.click("text=Back to task list")
        page.wait_for_selector(".fe-task-row", timeout=15000)
        same = page.locator(".fe-paper-group").nth(0)
        assert same.locator("h2").inner_text() == paper_title
        # open the NEXT task of the SAME paper
        opened = False
        for i in range(same.locator(".fe-task-row").count()):
            row = same.locator(".fe-task-row").nth(i)
            if "Submitted" not in row.inner_text():
                row.locator("button").click(); opened = True; break
        if opened:
            page.wait_for_selector(".fe-form", timeout=30000)
            page.wait_for_timeout(2000)
            form_text = " ".join(page.inner_text(".fe-form").split())
            check("carry-over: second task on the same paper does NOT ask again",
                  page.locator("#fam-area").count() == 0)
            check("carry-over: stored answers are shown",
                  "from your earlier task" in form_text and "moderate" in form_text,
                  form_text.split("\n")[1][:90] if "\n" in form_text else "")
            page.screenshot(path=str(SHOT / "08_task2_carried_over.png"), full_page=True)
        else:
            check("carry-over: a second task on the same paper was available", False)

    browser.close()

print("\n" + "=" * 60)
failed = [r for r in results if not r[1]]
print(f"{len(results) - len(failed)}/{len(results)} checks passed")
for name, ok, detail in failed:
    print(f"  FAILED: {name} -- {detail}")
print(f"screenshots: {SHOT.resolve()}")
sys.exit(1 if failed else 0)
