#!/usr/bin/env python3
"""Freeze one submission text per paper for the whole pilot, and check it once.

Every battle on a paper must see the SAME submission, or a fidelity judgement partly
reflects which parse the judge happened to get. So the text is written once, here, and
the judge script only reads it.

Which parse: the MinerU markdown, because the judge is asked to check claims about the
submission against the submission, and that needs the formulas and tables the paper
argues with. GROBID's section text drops display equations and table bodies; MinerU keeps
LaTeX math and table markup. It happens to be produced inside the DeepReviewer job
directory, but it is a PDF-to-markdown conversion of the submission and belongs to no
system's assessment -- and the SAME parser is used for both papers, so neither paper's
submission is better represented than the other's.

The check is printed, not assumed: character count, display and inline math, table rows,
section headings, and whether the text ends where the paper ends (references reached) or
was cut off. Read it once before running the pilot; it is the only chance to notice that
a judge was shown a truncated paper.

Usage
-----
  python eval/pilot_submission.py --check
  python eval/pilot_submission.py --write
"""
import argparse
import hashlib
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "eval" / "out" / "pilot_v1"

# paper_id -> the MinerU markdown of that paper's PDF
SOURCES = {
    "graphrag_when_to_use":
        "DeepReviewer-v2/data/jobs/f6481f23-5991-4642-9d03-c1fb98c85ba4/mineru_full.md",
    "transducing_language_models":
        "DeepReviewer-v2/data/jobs/2ecb0405-2604-4027-8f61-d5bb7e0509a6/mineru_full.md",
}


def stats(text: str) -> dict:
    return {
        "chars": len(text),
        "lines": len(text.splitlines()),
        "words": len(text.split()),
        "display_math": len(re.findall(r"\$\$", text)) // 2,
        "inline_math": len(re.findall(r"(?<!\$)\$(?!\$)[^$\n]{1,200}\$(?!\$)", text)),
        "table_rows": len(re.findall(r"^\s*\|.*\|\s*$", text, re.M)),
        "html_tables": len(re.findall(r"<table", text)),
        "headings": len(re.findall(r"^#{1,4}\s", text, re.M)),
        "images": len(re.findall(r"!\[", text)),
        "has_references": bool(re.search(r"^#{1,4}\s*(references|bibliography)\b", text,
                                         re.M | re.I)),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def main():
    ap = argparse.ArgumentParser(description="Freeze and check the pilot submission texts")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for paper, rel in SOURCES.items():
        src = REPO / rel
        if not src.exists():
            print(f"{paper}: SOURCE MISSING {src}")
            continue
        text = src.read_text(encoding="utf-8")
        st = stats(text)
        dst = OUT_DIR / f"{paper}__submission.txt"
        if args.write:
            dst.write_text(text, encoding="utf-8")
        print(f"\n=== {paper} ===")
        print(f"  source     : {rel}")
        print(f"  size       : {st['chars']:,} chars, {st['words']:,} words, "
              f"{st['lines']:,} lines")
        print(f"  math       : {st['display_math']} display, {st['inline_math']} inline")
        print(f"  tables     : {st['table_rows']} markdown rows, {st['html_tables']} html")
        print(f"  structure  : {st['headings']} headings, {st['images']} figures, "
              f"references section: {st['has_references']}")
        print(f"  sha256     : {st['sha256'][:16]}...")
        print(f"  tail       : ...{' '.join(text.split()[-14:])}")
        if args.write:
            print(f"  written    : {dst}")


if __name__ == "__main__":
    main()
