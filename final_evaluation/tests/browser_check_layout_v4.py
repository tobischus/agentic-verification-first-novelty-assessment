"""Browser check of the v4 report layout (battle_export reviewer-v4.1) in the study dashboard.

For each named paper it opens the agent-vs-linear task and checks BOTH report panels:

   1. the novelty summary is shown first; then the legend and the related-work table,
      both folded, above the claims
   2. every claim is one closed section whose row shows claim text, verdict and number of
      detailed comparisons with their overlap levels (matching the comparisons inside it)
   3. every detailed comparison of the report is present -- the count per panel matches the
      export's own count for agent and for linear
   4. each comparison shows source, version, assessment directly, and exactly two folded
      blocks: "Full comparison and quoted passages · N pairs" (N matching the pair labels
      inside), then "Evidence check and limitations"
   5. folded content is in the page (folding is not truncation)
   6. a related-work link opens the claim it points into and lands on the comparison
   7. paper-specific: claims without a detailed comparison stay visible and say so
      (Train-before-Test); an unsupported overlap level is named (EDIT-Bench)

Run it against a THROWAWAY copy of the study database -- opening tasks changes their
status. Log in with a test participant:

    DATABASE_URL=sqlite:///<copy>.sqlite python -m final_evaluation.cli serve --port 8012
    CHECK_BASE=http://127.0.0.1:8012 CHECK_CODE=<PV01 code> \
        python final_evaluation/tests/browser_check_layout_v4.py shots_v4/
"""
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("CHECK_BASE", "http://127.0.0.1:8012")
CODE = os.environ["CHECK_CODE"]
SHOT = Path(sys.argv[1] if len(sys.argv) > 1 else "shots_layout_v4")
SHOT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "novelty_assessment"))
import battle_export as be  # noqa: E402

PAPERS = [  # (paper key, a title fragment the task list shows)
    ("astabench", "Astabench"),
    ("output_supervision_can_obfuscate_the_chain_of", "Output Supervision"),
    ("train_before_test_harmonizes_language_model", "Train-Before-Test"),
    ("editbench", "Edit-Bench"),
]

results = []

UNREAD_TASK_STATUS = """async () => {
  const d = await (await fetch('/api/tasks', {credentials: 'same-origin'})).json();
  const t = d.tasks.find(x => !x.paper_read_confirmed && x.status !== 'submitted');
  if (!t) return null;
  const r = await fetch('/api/tasks/' + t.assignment_id, {credentials: 'same-origin'});
  return {status: r.status, required: d.reading_required};
}"""


def read_paper(page, group_sel, key):
    """The main study's reading step: tasks locked, questions first, plain PDF, confirm."""
    row = page.locator(f"{group_sel} .fe-read-row")
    if row.count() == 0:
        check(f"{key}: reading step shown above the paper's tasks", False)
        return
    if "done" in (row.get_attribute("class") or ""):
        return
    locked = page.locator(f"{group_sel} .fe-task-row button:disabled").count()
    total = page.locator(f"{group_sel} .fe-task-row").count()
    check(f"{key}: the paper's tasks are locked before reading", locked == total and total > 0,
          f"{locked}/{total}")
    srv = page.evaluate(UNREAD_TASK_STATUS)
    check(f"{key}: the server refuses a task of an unread paper", srv and srv["status"] == 409, str(srv))
    row.locator("button").click()
    page.wait_for_selector("#read-fam-area", timeout=20000)
    check(f"{key}: no document before the background questions are answered",
          page.locator(".fe-read-pdf").count() == 0)
    page.select_option("#read-fam-area", "moderate")
    page.select_option("#read-fam-read", "false")
    page.wait_for_selector(".fe-read-pdf .pdfpage", timeout=30000)
    page.wait_for_timeout(1500)
    check(f"{key}: the submission is shown plain, without highlights",
          page.locator(".fe-read-pdf .pdfhl").count() == 0)
    btn = page.locator(".fe-read-confirm button")
    check(f"{key}: continuing needs the checkbox", btn.is_disabled())
    page.check(".fe-read-confirm input[type=checkbox]")
    btn.click()
    page.wait_for_selector(".fe-task-row", timeout=20000)
    unlocked = page.locator(f"{group_sel} .fe-task-row button:disabled").count() == 0
    check(f"{key}: the paper's tasks open after the confirmation", unlocked)


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


def expected(key):
    """Per variant: comparisons per claim and number of open-point rows, from the export."""
    out = {}
    for v in ("agent", "linear"):
        md = be.build("data", key, variant=v)
        per_claim = [0 if x == "none recorded" else int(x.split()[0])
                     for x in re.findall(r"^\*\*Detailed comparisons:\*\* (.+)$", md, re.M)]
        out[v] = {"per_claim": per_claim,
                  "open_rows": len(re.findall(r"^\*\*Open points:\*\*", md, re.M)),
                  "text": md}
    return out


def check_panel(page, panel, tag, exp_by_variant):
    claims = panel.locator("details.lay-claim")
    n_claims = claims.count()
    per_claim = [claims.nth(i).locator(".lay-cmp").count() for i in range(n_claims)]
    variant = next((v for v, e in exp_by_variant.items() if e["per_claim"] == per_claim), None)
    check(f"{tag}: comparisons per claim match the export of one variant",
          variant is not None, f"{per_claim}")
    if variant is None:
        return None
    exp = exp_by_variant[variant]
    check(f"{tag}: every claim starts closed",
          panel.locator("details.lay-claim[open]").count() == 0, f"{n_claims} claims")
    check(f"{tag}: every fold starts closed",
          panel.locator("details.lay-fold[open]").count() == 0)
    summ = panel.locator(".rr-body > .rr-h2").first
    first_claim = claims.first
    check(f"{tag}: the novelty summary comes first, above the claims",
          summ.count() and summ.inner_text().strip() == "Novelty summary"
          and summ.bounding_box()["y"] < first_claim.bounding_box()["y"])
    legend = panel.locator("details.lay-fold.blk-legend")
    matrix = panel.locator("details.lay-fold.blk-matrix")
    check(f"{tag}: legend, then related-work table, both folded, between summary and claims",
          legend.count() == 1 and matrix.count() == 1
          and summ.bounding_box()["y"] < legend.bounding_box()["y"]
          < matrix.bounding_box()["y"] < first_claim.bounding_box()["y"])
    check(f"{tag}: no coverage section any more",
          panel.locator("details.lay-fold.blk-coverage").count() == 0
          and "Coverage and limitations" not in panel.evaluate("e => e.textContent"))

    rows_ok, count_ok, open_rows = True, True, 0
    for i in range(n_claims):
        s = claims.nth(i).locator("> summary")
        t = s.inner_text()
        rows_ok &= (f"Claim {i + 1}" in t and s.locator(".lay-verdict .as-pill").count() == 1
                    and "Detailed comparisons:" in t
                    and (per_claim[i] == 0 or re.search(r"Detailed comparisons:\s*\d+ \(", t))
                    and len(s.locator("p").nth(0).inner_text().strip()) > 20)
        m = re.search(r"Detailed comparisons:\s*(\d+|none recorded)", t)
        shown = 0 if (m and m.group(1) == "none recorded") else int(m.group(1)) if m else -1
        count_ok &= shown == per_claim[i]
        open_rows += s.locator(".lay-open").count()
    check(f"{tag}: each claim row shows number, claim text, verdict pill, count with levels",
          rows_ok)
    check(f"{tag}: the count on the row equals the comparisons inside", count_ok)
    check(f"{tag}: no open-points line on the claim rows", open_rows == 0, f"{open_rows}")
    # v4.4: the claim text is the link to its anchor passage in the submission PDF --
    # clicking it shows the passage and does NOT fold the claim open.
    jumps = panel.locator("details.lay-claim > summary a.claim-jump")
    check(f"{tag}: every claim text links to its anchor in the PDF", jumps.count() == n_claims,
          f"{jumps.count()}/{n_claims}")
    check(f"{tag}: no separate submission-passages section any more",
          panel.locator("details.lay-fold.blk-passages").count() == 0)
    if jumps.count():
        jumps.first.click()
        page.wait_for_timeout(800)
        check(f"{tag}: clicking the claim text marks the passage and leaves the claim closed",
              "active" in (jumps.first.get_attribute("class") or "")
              and panel.locator("details.lay-claim[open]").count() == 0)
        overlay = page.locator(".fe-overlay")
        if overlay.count():
            page.wait_for_timeout(1500)
            page.screenshot(path=str(SHOT / f"{tag.replace('[', '_').replace(']', '')}_claim_anchor_pdf.png"))
            overlay.click(position={"x": 4, "y": 4})
            page.wait_for_timeout(400)

    cmps = panel.locator(".lay-cmp")
    shape_bad, pairs_bad = [], []
    for i in range(cmps.count()):
        c = cmps.nth(i)
        # textContent: the comparisons sit inside claims that start closed, and innerText
        # is empty for anything a closed <details> does not render.
        direct = c.evaluate("e => e.textContent")
        folds = c.locator("> details.lay-fold")
        # textContent, not innerText: the fold titles are styled in capitals, and innerText
        # returns what CSS displays rather than the text the export wrote.
        titles = [" ".join(folds.nth(j).locator("> summary").evaluate("e => e.textContent").split())
                  for j in range(folds.count())]
        if not (("Source used:" in direct) and ("Assessment:" in direct) and len(titles) == 2
                and titles[0].startswith("Full comparison and quoted passages")
                and titles[1] == "Evidence check and limitations"):
            shape_bad.append(i)
            continue
        n = int(re.search(r"·\s*(\d+)\s+pairs?", titles[0]).group(1))
        body = folds.nth(0).evaluate("e => e.textContent")
        labels = re.findall(r"Pair (\d+) [—-]", body)
        if sorted(map(int, labels)) != list(range(1, n + 1)):
            pairs_bad.append((i, n, labels[:5]))
    check(f"{tag}: every comparison: source, assessment, then the two folds, pairs first",
          not shape_bad, f"{cmps.count()} comparisons; bad={shape_bad[:5]}")
    check(f"{tag}: pair count in the fold title matches the numbered pairs inside",
          not pairs_bad, f"{pairs_bad[:3]}")

    # Folding is not truncation: a folded block's text is in the page.
    reasoning = re.findall(r"^\*\*Status:\*\* [^\n]+\n\n(?:\*\*[^\n]+\n\n)*([^*#>\n][^\n]{60,})",
                           exp["text"], re.M)
    sample = reasoning[0][:80] if reasoning else ""
    whole = panel.evaluate("e => e.textContent")
    check(f"{tag}: folded evidence-check text is present while folded",
          bool(sample) and " ".join(sample.split()) in " ".join(whole.split()), sample[:50])
    return variant


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome")
    ctx = browser.new_context(viewport={"width": 1700, "height": 1000})
    page = ctx.new_page()
    page.on("pageerror", lambda e: check("no JS page error", False, str(e)))
    page.goto(BASE, wait_until="networkidle")
    check("login page: no contact line, no pilot banner",
          page.locator(".fe-contact").count() == 0 and page.locator(".fe-pilot-banner").count() == 0)
    page.fill("#code", CODE)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector(".fe-instructions, .fe-task-row", timeout=25000)
    if page.locator(".fe-instructions").count():
        page.check("input[type=checkbox] >> nth=0")
        page.check("input[type=checkbox] >> nth=1")
        page.select_option("select >> nth=0", "1-5")
        page.select_option("select >> nth=1", "no")
        page.locator("button:has-text('Continue')").last.click()
        page.wait_for_load_state("networkidle")
    page.wait_for_selector(".fe-task-row", timeout=20000)

    for key, fragment in PAPERS:
        exp = expected(key)
        opened = False
        # The list groups tasks under a paper heading; the rows themselves are blinded.
        group_sel = f".fe-paper-group:has(h2:text-matches('{re.escape(fragment)}', 'i'))"
        read_paper(page, group_sel, key)
        n_rows = page.locator(f"{group_sel} .fe-task-row").count()
        for i in range(n_rows):
            row = page.locator(f"{group_sel} .fe-task-row").nth(i)
            row.locator("button").click()
            page.wait_for_selector(".fe-form", timeout=30000)
            page.wait_for_timeout(2500)
            # main_study_v2: every task is the agent against one external system, so the
            # task to check is one where exactly one panel is a v4 report (the other is an
            # external report -- markdown or PDF, never grouped).
            one_v4 = ("() => [...document.querySelectorAll('.fe-report-panel')]"
                      ".filter(p => p.querySelector('.lay-claim')).length === 1")
            try:
                page.wait_for_function(one_v4, timeout=12000)
                opened = True
                break
            except Exception:
                pass
            page.locator(".fe-topbar button:has-text('Task list')").click()
            page.wait_for_selector(".fe-task-row", timeout=20000)
        check(f"{key}: an agent-vs-external task found, agent rendered in v4", opened)
        if not opened:
            continue
        panels = page.locator(".fe-report-panel")
        side = 0 if panels.nth(0).locator(".lay-claim").count() else 1
        variant = check_panel(page, panels.nth(side), f"{key}[{'AB'[side]}]", exp)
        check(f"{key}: the v4 panel is the agent report", variant == "agent", f"{variant}")
        # main_study_v2 fixes: no pilot banner, no live link out of any report.
        check(f"{key}: no development-pilot banner in the main study",
              page.locator(".fe-pilot-banner").count() == 0)
        ext = page.locator(".fe-report-panel a[href^='http']").count()
        check(f"{key}: no clickable external link in either report (PROTOCOL section 4)",
              ext == 0, f"{ext} links")
        page.screenshot(path=str(SHOT / f"{key}_01_overview.png"))

        # Jump from the related-work matrix into a comparison: claim unfolds, target shown.
        a = panels.nth(side)
        a.locator("details.lay-fold.blk-matrix > summary").click()
        link = a.locator("details.lay-fold.blk-matrix a.as-jump").first
        href = link.get_attribute("href")
        link.click()
        page.wait_for_timeout(900)
        target = page.locator(f"[id='{href[1:]}']")
        claim_open = target.evaluate("e => !!e.closest('details.lay-claim') && e.closest('details.lay-claim').open")
        check(f"{key}: a matrix link opens its claim and reaches the comparison",
              target.count() == 1 and claim_open and target.is_visible(), href)
        page.screenshot(path=str(SHOT / f"{key}_02_jump.png"))
        # open both folds of that comparison, for the record
        for j in range(target.locator("> details.lay-fold").count()):
            target.locator("> details.lay-fold > summary").nth(j).click()
        page.wait_for_timeout(400)
        target.scroll_into_view_if_needed()
        page.screenshot(path=str(SHOT / f"{key}_03_folds_open.png"))

        if key == "train_before_test_harmonizes_language_model":
            none_rows = page.locator("details.lay-claim > summary:has-text('none recorded')").count()
            check(f"{key}: claims without a detailed comparison stay visible and say so",
                  none_rows >= 1, f"{none_rows} rows")
        if key == "editbench":
            t = page.locator(".fe-report-panel").evaluate_all(
                "els => els.map(e => e.textContent).join(' ')")
            check(f"{key}: an unsupported overlap level is named",
                  "The evidence check does not support this overlap level." in t)

        page.locator(".fe-topbar button:has-text('Task list')").click()
        page.wait_for_selector(".fe-task-row", timeout=20000)

    browser.close()

passed = sum(1 for _, ok, _ in results if ok)
print("\n" + "=" * 62)
print(f"{passed}/{len(results)} checks passed")
print(f"screenshots: {SHOT.resolve()}")
sys.exit(0 if passed == len(results) else 1)
