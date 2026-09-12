#!/usr/bin/env python3
"""Cut DeepReviewer 2.0's novelty assessment out of its full review, by a fixed rule.

DeepReviewer writes a complete peer review -- strengths, weaknesses, experiment plans,
writing outlines, scores. The other four systems in the pilot assess novelty and nothing
else. Comparing their novelty reports against DeepReviewer's entire review would compare
scope, not novelty assessment, so one section of it is used.

THE RULE, fixed before either paper was extracted and applied identically to both:

  1. take the section `## Novelty Verification & Related-Work Matrix` in full, from its
     heading up to the next `## ` heading -- every subsection, table, conclusion and
     diagram inside it, verbatim and in order;
  2. collect every `[n]` citation marker that appears in that text;
  3. append those numbered entries from the report's own `## References` section, so the
     markers stay resolvable and the report keeps its references, as the pilot requires.

Nothing is rewritten, shortened, reordered, or dropped for being inconvenient, and no
sentence is added. The restriction to one section is deliberate information loss and is
reported as such: it is the only way to put this system beside novelty-only systems.

Usage
-----
  python eval/extract_deepreviewer.py --job DeepReviewer-v2/data/jobs/<id> \
      --out comparison/outputs/<paper>__deepreviewer.md
"""
import argparse
import re
from pathlib import Path

SECTION = "## Novelty Verification & Related-Work Matrix"
REFERENCES = "## References"


def extract(report: str) -> str:
    lines = report.splitlines()

    start = next((i for i, ln in enumerate(lines) if ln.strip() == SECTION), None)
    if start is None:
        raise SystemExit(f"section not found: {SECTION}")
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("## ")), len(lines))
    body = lines[start:end]

    # Markers as they appear in the text: [2], [3], ... Ranges or comma lists inside one
    # bracket ("[2], [3]") are already separate brackets in this report format.
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", "\n".join(body))}

    ref_start = next((i for i, ln in enumerate(lines) if ln.strip() == REFERENCES), None)
    refs = []
    if ref_start is not None and cited:
        ref_end = next((i for i in range(ref_start + 1, len(lines))
                        if lines[i].startswith("## ")), len(lines))
        for ln in lines[ref_start + 1:ref_end]:
            m = re.match(r"\s*\[(\d+)\]", ln)
            if m and int(m.group(1)) in cited:
                refs.append(ln.rstrip())

    out = [ln.rstrip() for ln in body]
    while out and not out[-1]:
        out.pop()
    if refs:
        out += ["", REFERENCES, ""]
        for r in refs:
            out += [r, ""]
    return "\n".join(out).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description="Extract DeepReviewer's novelty section")
    ap.add_argument("--job", required=True, help="a DeepReviewer job directory")
    ap.add_argument("--report", default="final_report.md")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    src = Path(args.job) / args.report
    text = extract(src.read_text(encoding="utf-8"))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"written: {out} ({len(text)} chars, {len(text.split())} words) from {src}")


if __name__ == "__main__":
    main()
