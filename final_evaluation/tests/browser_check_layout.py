"""Browser check of the new Summary/report layout in the study dashboard.

   1. "Related work examined": substantial-or-higher rows highlighted, assessments linked
   2. "Closest comparisons": Source carries the title, two columns only, linked assessment
   3. clicking an assessment jumps to (and unfolds) that exact comparison
   4. inside a comparison: metadata + assessment first, prior-work summary folded,
      Comparison open, supporting evidence pairs open, unused pairs and the
      evidence-check record folded, and each block visually delimited
   5. nothing lost: every folded block still holds its text

Run it against a THROWAWAY database, never the study one -- it fills in a task and
clicks through report panels:

    python -m final_evaluation.cli init-db            # DATABASE_URL=sqlite:///...test.sqlite
    python -m final_evaluation.cli seed-pilot
    python -m final_evaluation.cli create-participants --study dashboard_pilot_v1 --count 2
    python -m final_evaluation.cli serve --port 8011
    CHECK_BASE=http://127.0.0.1:8011 CHECK_CODES=<the codes csv>         python final_evaluation/tests/browser_check_layout.py shots/

Playwright's own Chromium build is not downloaded on this machine, so the system Chrome
is driven instead (`channel="chrome"`) -- same engine, real browser.
"""
import csv
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("CHECK_BASE", "http://127.0.0.1:8010")
SHOT = Path(sys.argv[1] if len(sys.argv) > 1 else "shots_layout")
SHOT.mkdir(parents=True, exist_ok=True)
CODES = Path(os.environ.get(
    "CHECK_CODES",
    "final_evaluation/private/participant_codes__dashboard_pilot_v1__test_study3.csv"))

with open(CODES, encoding="utf-8") as fh:
    code = next(r["code"] for r in csv.DictReader(fh) if r["code_display"] == "R01")

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome")
    ctx = browser.new_context(viewport={"width": 1600, "height": 950})
    page = ctx.new_page()
    page.on("pageerror", lambda e: check("no JS page error", False, str(e)))

    page.goto(BASE, wait_until="networkidle")
    page.fill("#code", code)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    # consent + instructions
    page.wait_for_selector(".fe-instructions, .fe-task-row", timeout=25000)
    if page.locator(".fe-instructions").count():
        page.check("input[type=checkbox] >> nth=0")
        page.check("input[type=checkbox] >> nth=1")
        page.select_option("select >> nth=0", "1-5")
        page.select_option("select >> nth=1", "no")
        page.locator("button:has-text('Continue')").last.click()
        page.wait_for_load_state("networkidle")

    page.wait_for_selector(".fe-task-row", timeout=20000)
    # Open the agent-linear task, i.e. one where BOTH panels are battle_export markdown.
    opened = False
    for i in range(page.locator(".fe-task-row").count()):
        row = page.locator(".fe-task-row").nth(i)
        row.locator("button").click()
        page.wait_for_selector(".fe-form", timeout=30000)
        page.wait_for_timeout(2500)
        if page.locator(".rr-doc").count() == 2:
            opened = True
            break
        page.locator(".fe-topbar button.link").click()
        page.wait_for_selector(".fe-task-row", timeout=20000)
    check("found a task with two markdown reports", opened)

    panel = page.locator(".fe-report-panel").nth(0)
    page.screenshot(path=str(SHOT / "01_task_open.png"), full_page=False)

    # ---------- 1. Related work examined ----------
    tables = panel.locator(".rr-table")
    check("report renders the overview tables", tables.count() >= 2, f"{tables.count()} tables")
    related = tables.nth(0)
    strong_rows = related.locator("tr.as-cell-row")
    check("related work: substantial-or-higher rows are highlighted",
          strong_rows.count() > 0, f"{strong_rows.count()} highlighted rows")
    # every highlighted row must actually contain a substantial/same assessment
    bad = []
    for i in range(strong_rows.count()):
        txt = strong_rows.nth(i).inner_text()
        if "substantial overlap" not in txt and "same contribution" not in txt:
            bad.append(txt[:60])
    check("related work: no row highlighted without substantial-or-higher", not bad, "; ".join(bad))
    # and no such row is left un-highlighted
    missed = 0
    for i in range(related.locator("tbody tr").count()):
        r = related.locator("tbody tr").nth(i)
        t = r.inner_text()
        if ("substantial overlap" in t or "same contribution" in t) and "as-cell-row" not in (
                r.get_attribute("class") or ""):
            missed += 1
    check("related work: every substantial-or-higher row is highlighted", missed == 0, f"{missed} missed")

    cells = related.locator("td.as-cell")
    links = related.locator("td.as-cell a.as-jump")
    check("related work: assessment cells are colour-classified",
          cells.count() > 0, f"{cells.count()} assessment cells")
    check("related work: assessments carry a jump link",
          links.count() > 0, f"{links.count()} of {cells.count()} cells linked")
    # a linked cell's href must resolve to an element that exists in THIS panel
    hrefs = [links.nth(i).get_attribute("href") for i in range(links.count())]
    dead = [h for h in hrefs if page.locator(f"[id='{h[1:]}']").count() == 0]
    check("related work: no dead jump link", not dead, f"{len(dead)} dead: {dead[:3]}")
    check("related work: links are panel-scoped (a-prefixed ids)",
          all(h.startswith("#a-cmp-") for h in hrefs), hrefs[0] if hrefs else "")

    # ---------- 2. Closest comparisons ----------
    closest = panel.locator(".rr-table").nth(1)
    head = [h.strip() for h in closest.locator("th").all_inner_texts()]
    check("closest comparisons: exactly Source + Assessment", head == ["Source", "Assessment"], str(head))
    first_src = closest.locator("tbody tr").nth(0).locator("td").nth(0).inner_text()
    check("closest comparisons: Source carries the title, not just R#",
          first_src.strip().startswith("R") and "—" in first_src, first_src[:70])
    body_text = " ".join(closest.inner_text().split())
    check("closest comparisons: Shared contribution / Reported difference dropped",
          "Shared contribution" not in body_text and "Reported difference" not in body_text)
    check("closest comparisons: assessment coloured and linked",
          closest.locator("td.as-cell a.as-jump").count() == closest.locator("tbody tr").count(),
          f"{closest.locator('td.as-cell a.as-jump').count()} links / "
          f"{closest.locator('tbody tr').count()} rows")
    page.screenshot(path=str(SHOT / "02_tables.png"), full_page=False)

    # ---------- 3. the jump ----------
    target = hrefs[0][1:]
    before_open = page.locator(f"details[id='{target}']").get_attribute("open")
    links.nth(0).click()
    page.wait_for_timeout(900)
    det = page.locator(f"details[id='{target}']")
    check("jump: the linked comparison exists as a collapsible section", det.count() == 1)
    check("jump: it was collapsed and the click unfolded it",
          before_open is None and det.get_attribute("open") is not None,
          f"before={before_open} after={det.get_attribute('open')}")
    box = det.locator("> summary").bounding_box()
    check("jump: the section is scrolled into view", box is not None and 0 <= box["y"] <= 950,
          str(box and round(box["y"])))
    page.screenshot(path=str(SHOT / "03_after_jump.png"), full_page=False)

    # ---------- 4. order and folding inside a comparison ----------
    kinds = det.locator(".blk")
    order = [(kinds.nth(i).get_attribute("class"), kinds.nth(i).get_attribute("open"))
             for i in range(kinds.count())]
    kind_of = lambda c: next((k for k in ("priorwork", "comparison", "pairs", "unused", "check")
                              if f"blk-{k}" in c), "?")
    seq = [kind_of(c) for c, _o in order]
    check("comparison: blocks appear in the asked order",
          seq[:3] == ["priorwork", "comparison", "pairs"], str(seq))
    folded = {kind_of(c) for c, o in order if o is None}
    opened_ = {kind_of(c) for c, o in order if o is not None}
    check("comparison: prior work summary starts folded", "priorwork" in folded, str(folded))
    check("comparison: Comparison and the supporting pairs start open",
          {"comparison", "pairs"} <= opened_, str(opened_))
    check("comparison: unused pairs and the evidence-check record start folded",
          "unused" in folded or "unused" not in seq, str(folded))
    check("comparison: the evidence-check record starts folded", "check" in folded, str(folded))

    # the assessment comes BEFORE the first block, and is coloured
    body = det.locator(".rr-detail-body")
    pill_in_body = body.locator("p.as-assess .as-pill")
    check("comparison: an Assessment line with a colour pill is present",
          pill_in_body.count() >= 1, f"{pill_in_body.count()}")
    if pill_in_body.count() and kinds.count():
        y_pill = pill_in_body.nth(0).bounding_box()["y"]
        y_blk = kinds.nth(0).bounding_box()["y"]
        check("comparison: metadata + assessment stand above the first block", y_pill < y_blk,
              f"pill@{round(y_pill)} block@{round(y_blk)}")
    check("comparison: the folded section's own summary shows its assessment in colour",
          det.locator("> summary .as-pill").count() == 1)

    # blocks are visually delimited from one another
    tints = set()
    for i in range(kinds.count()):
        tints.add(kinds.nth(i).evaluate(
            "el => getComputedStyle(el).backgroundColor + '|' + getComputedStyle(el).borderLeftColor"))
    check("comparison: each block has its own tint", len(tints) == kinds.count(),
          f"{len(tints)} distinct of {kinds.count()} blocks")

    # ---------- 5. nothing lost ----------
    prior = det.locator(".blk-priorwork")
    # text_content(), not inner_text(): a closed <details> renders nothing, and the point
    # of this check is that the text sits in the DOM even while the block is folded.
    folded_text = (prior.locator("> .rr-sub-body").text_content(timeout=5000) or "").strip()
    check("no loss: the folded prior-work summary still holds its text",
          len(folded_text) > 40, f"{len(folded_text)} chars while folded")
    prior.locator("> summary").click()
    page.wait_for_timeout(400)
    check("no loss: it opens on click", prior.get_attribute("open") is not None)
    check("no loss: it contains a quote, not new prose",
          prior.locator(".rz-quote").count() >= 1, f"{prior.locator('.rz-quote').count()} quotes")
    check("no loss: no text was added -- the heading is the export's own",
          prior.locator("> summary").inner_text().strip() == "Prior work summary",
          prior.locator("> summary").inner_text().strip())
    unused_blk = det.locator(".blk-unused")
    if unused_blk.count():
        unused_blk.locator("> summary").click()
        page.wait_for_timeout(300)
        check("no loss: the unused-pairs block keeps the original pair numbers",
              "Pair " in unused_blk.inner_text(), unused_blk.inner_text()[:60])
    check_blk = det.locator(".blk-check")
    check_blk.locator("> summary").click()
    page.wait_for_timeout(300)
    check("no loss: the evidence-check record opens with its status",
          "Status" in check_blk.inner_text(), check_blk.inner_text()[:60])
    page.screenshot(path=str(SHOT / "04_comparison_expanded.png"), full_page=False)

    # ---------- the other panel is styled the same way ----------
    other = page.locator(".fe-report-panel").nth(1)
    check("both panels get the same treatment",
          other.locator("td.as-cell a.as-jump").count() > 0 and other.locator(".blk").count() > 0,
          f"{other.locator('td.as-cell a.as-jump').count()} links, {other.locator('.blk').count()} blocks")
    b_links = other.locator("td.as-cell a.as-jump")
    b_href = b_links.nth(0).get_attribute("href")
    check("panel B's links stay inside panel B", b_href.startswith("#b-cmp-"), b_href)
    b_links.nth(0).click()
    page.wait_for_timeout(700)
    check("panel B's jump unfolds panel B's section, not panel A's",
          page.locator(f"details[id='{b_href[1:]}'][open]").count() == 1)
    page.screenshot(path=str(SHOT / "05_panel_b.png"), full_page=False)

    browser.close()

print("\n" + "=" * 62)
failed = [r for r in results if not r[1]]
print(f"{len(results) - len(failed)}/{len(results)} checks passed")
for name, ok, detail in failed:
    print(f"  FAILED: {name} -- {detail}")
print(f"screenshots: {SHOT.resolve()}")
sys.exit(1 if failed else 0)
