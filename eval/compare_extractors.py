#!/usr/bin/env python3
"""MinerU against GROBID on the same submissions, measured rather than asserted.

Both produce "the text of the paper", and the E1 judge is shown exactly one of them. The
claim in eval/pilot_submission.py is that GROBID's section text drops display equations and
table bodies while MinerU keeps them. This checks that claim, and the broader question it
sits inside: how much of the paper does each extractor actually keep?

Method -- a neutral third reference
-----------------------------------
Neither extractor can be the yardstick for the other. PyMuPDF reads the PDF's own text
objects with no layout model, no section logic and no ML: it is not a good reading order,
but it is close to "every character the PDF contains". So it is the reference, and each
extractor is scored on how much of it survives.

Recall is measured on WORD WINDOWS, not characters: the reference text is cut into
overlapping windows of `--window` words, and a window counts as retained if its normalised
word sequence occurs in the normalised candidate. Normalisation folds case, ligatures and
all punctuation, so a hyphenation or quoting difference does not count as lost text, while
a dropped sentence does. Reading order is deliberately not scored -- both tools reorder
columns, and the judge reads prose, not coordinates.

Math-carrying lines are scored separately, because that is where the two are expected to
differ and an overall average would hide it.

What this does NOT measure: whether the retained text reads well, whether tables keep their
structure, or whether a formula is transcribed correctly rather than merely present. Those
need eyes on the output -- `sample_missing` in the JSON is there to start that.

Usage
-----
  python eval/compare_extractors.py                     # all papers with both texts
  python eval/compare_extractors.py --only astabench --sample 600
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MINERU_DIR = REPO / "eval" / "out" / "human_study" / "submission_text"
OUT = REPO / "eval" / "out" / "human_study" / "extractor_comparison"

_LIG = str.maketrans({"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff",
                      "ﬃ": "ffi", "ﬄ": "ffl",
                      "–": "-", "—": "-", "’": "'", "‘": "'",
                      "“": '"', "”": '"'})

#: characters that mark a line as carrying mathematics rather than prose
_MATH = set("=+−-×÷≤≥≈≠∑∏∫∂∇"
            "√∞αβγδεθλμσπ"
            "φψωΔΩ^_|⟨⟩")


def norm_words(text: str) -> list[str]:
    """Lowercased alphanumeric word sequence: what survives hyphenation and typography."""
    t = text.translate(_LIG).lower()
    t = re.sub(r"-\s*\n\s*", "", t)          # rejoin words broken across lines
    return re.findall(r"[a-z0-9]+", t)


def pdf_reference(pdf: Path) -> str:
    import fitz
    d = fitz.open(pdf)
    return "\n".join(d[i].get_text() for i in range(d.page_count))


def grobid_text(key: str) -> str | None:
    p = REPO / "data" / key / f"{key}_fulltext.json"
    if not p.is_file():
        return None
    secs = json.loads(p.read_text(encoding="utf-8")).get("sections") or []
    return "\n\n".join(f"## {s.get('section','')}\n{s.get('text','')}" for s in secs)


def mineru_text(key: str) -> str | None:
    p = MINERU_DIR / f"{key}__submission.txt"
    return p.read_text(encoding="utf-8") if p.is_file() else None


def recall(ref_words, cand_words, window: int, sample: int, pick=None):
    """Fraction of reference word-windows that occur in the candidate.

    The candidate is indexed once as a string of space-joined words, so each window is a
    single substring test -- linear in the candidate, not quadratic over windows."""
    hay = " " + " ".join(cand_words) + " "
    n = len(ref_words) - window
    if n <= 0:
        return (0.0, 0, [])
    idx = list(range(0, n)) if pick is None else [i for i in pick if 0 <= i < n]
    if len(idx) > sample:
        step = len(idx) / sample
        idx = [idx[int(i * step)] for i in range(sample)]
    miss, hit = [], 0
    for i in idx:
        w = " " + " ".join(ref_words[i:i + window]) + " "
        if w in hay:
            hit += 1
        elif len(miss) < 12:
            miss.append(w.strip())
    return (hit / len(idx) if idx else 0.0, len(idx), miss)


def unique_windows(ref_words, window: int, max_repeats: int = 2):
    """Offsets of reference windows whose word sequence is not page furniture.

    A running header, an arXiv stamp or a footer repeats on every page, so it contributes
    dozens of reference windows. An extractor that strips it -- which is the RIGHT thing to
    do for a text a judge will read -- is then scored as having lost the paper dozens of
    times over, while one that keeps every repetition is rewarded. Windows occurring more
    than `max_repeats` times in the paper are therefore excluded from the content measure.
    They are still counted in `recall_all`, so the size of the effect stays visible.
    """
    from collections import Counter
    seqs = [" ".join(ref_words[i:i + window]) for i in range(max(len(ref_words) - window, 0))]
    freq = Counter(seqs)
    return [i for i, s in enumerate(seqs) if freq[s] <= max_repeats]


def math_windows(ref_text: str, window: int):
    """Word offsets of windows starting inside a mathematics-carrying line.

    Lines are classified BEFORE normalisation, because normalisation is exactly what
    removes the symbols that identify them."""
    offsets, pos = [], 0
    for line in ref_text.splitlines():
        wl = len(norm_words(line))
        syms = sum(1 for c in line if c in _MATH)
        if wl and syms >= 3 and syms / max(len(line), 1) > 0.04:
            offsets.extend(range(pos, pos + max(wl - window, 1)))
        pos += wl
    return offsets


def compare(key: str, pdf: Path, window: int, sample: int):
    gt, mt = grobid_text(key), mineru_text(key)
    if gt is None or mt is None:
        return {"paper": key,
                "skipped": f"missing {'grobid' if gt is None else 'mineru'} text"}
    ref_text = pdf_reference(pdf)
    ref = norm_words(ref_text)
    mw = math_windows(ref_text, window)
    uw = unique_windows(ref, window)
    row = {"paper": key, "pdf": pdf.relative_to(REPO).as_posix(),
           "reference_words": len(ref), "math_window_offsets": len(mw),
           "unique_window_offsets": len(uw), "systems": {}}
    for name, text in (("mineru", mt), ("grobid", gt)):
        cw = norm_words(text)
        r_all, n_all, _ = recall(ref, cw, window, sample)
        r_uni, n_uni, miss = recall(ref, cw, window, sample, pick=uw)
        if mw:
            r_math, n_math, miss_math = recall(ref, cw, window, sample, pick=mw)
        else:
            r_math, n_math, miss_math = None, 0, []
        row["systems"][name] = {
            "chars": len(text), "words": len(cw),
            "words_vs_reference": round(len(cw) / len(ref), 3) if ref else None,
            "recall_all": round(r_all, 4), "windows_tested": n_all,
            # The content measure: page furniture excluded. `recall_all` is kept beside it
            # so the difference between the two says how much furniture the paper carries.
            "recall_content": round(r_uni, 4), "content_windows_tested": n_uni,
            "recall_math_lines": (round(r_math, 4) if r_math is not None else None),
            "math_windows_tested": n_math,
            "display_math_markup": len(re.findall(r"\$\$", text)) // 2,
            "table_rows_markup": len(re.findall(r"^\s*\|.*\|\s*$", text, re.M)),
            "html_tables": len(re.findall(r"<table", text)),
            "headings": len(re.findall(r"^#{1,4}\s", text, re.M)),
            "reaches_references": bool(re.search(r"^#{1,4}\s*(references|bibliography)\b",
                                                 text, re.M | re.I)),
            "sample_missing": miss[:6], "sample_missing_math": miss_math[:6],
        }
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="")
    ap.add_argument("--window", type=int, default=8, help="words per window (default 8)")
    ap.add_argument("--sample", type=int, default=800, help="windows tested per text")
    args = ap.parse_args()

    sys.path.insert(0, str(REPO / "eval"))
    from human_study_submission_text import papers
    sel = papers()
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        sel = {k: v for k, v in sel.items() if k in want}

    rows = []
    for key, pdf in sel.items():
        r = compare(key, pdf, args.window, args.sample)
        if r:
            rows.append(r)
            print(f"{key}: {r.get('skipped') or 'done'}", flush=True)

    good = [r for r in rows if not r.get("skipped")]
    print()
    head = (f"{'paper':<44}{'MinerU rec':>11}{'GROBID rec':>11}"
            f"{'MinerU math':>12}{'GROBID math':>12}"
            f"{'MinerU w/ref':>13}{'GROBID w/ref':>13}")
    print(head)
    print("-" * len(head))

    def pct(x):
        return "    --" if x is None else f"{x * 100:5.1f}%"

    for r in good:
        m, g = r["systems"]["mineru"], r["systems"]["grobid"]
        print(f"{r['paper'][:42]:<44}{pct(m['recall_content']):>11}{pct(g['recall_content']):>11}"
              f"{pct(m['recall_math_lines']):>12}{pct(g['recall_math_lines']):>12}"
              f"{m['words_vs_reference']:>13}{g['words_vs_reference']:>13}")

    if good:
        def avg(sysname, field):
            vals = [r["systems"][sysname][field] for r in good
                    if r["systems"][sysname][field] is not None]
            return statistics.mean(vals) if vals else 0.0

        print("-" * len(head))
        print(f"{'MITTEL':<44}{avg('mineru','recall_content')*100:10.1f}%"
              f"{avg('grobid','recall_content')*100:10.1f}%"
              f"{avg('mineru','recall_math_lines')*100:11.1f}%"
              f"{avg('grobid','recall_math_lines')*100:11.1f}%"
              f"{avg('mineru','words_vs_reference'):13.3f}"
              f"{avg('grobid','words_vs_reference'):13.3f}")
        print("\nrec   = Anteil der Wortfenster aus der PDF, die im Extrakt wiederzufinden sind.")
        print("math  = dasselbe, nur fuer Fenster aus formeltragenden Zeilen.")
        print("w/ref = Woerter des Extrakts geteilt durch Woerter der PDF.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "comparison.json").write_text(
        json.dumps({"window": args.window, "sample": args.sample, "papers": rows},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\ngeschrieben: {(OUT / 'comparison.json').relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
