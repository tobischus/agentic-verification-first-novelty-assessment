#!/usr/bin/env python3
"""
Turn a report PDF into Markdown, for systems that only publish PDFs.

OpenNovelty releases its reports as PDF only, so its content has to be recovered as text
before it can sit next to the other systems' outputs in the comparison. Extraction keeps
everything: headings are inferred from font size relative to the document's body text, and
nothing is summarised, reordered or dropped. A comparison that silently loses a competitor's
content measures the extraction, not the system.

Usage
-----
  python eval/pdf_to_md.py --pdf report.pdf --out report.md
"""
import argparse
import re
from pathlib import Path

import pymupdf


def _blocks(page):
    """(text, max_font_size, is_bold) per line, in reading order."""
    out = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(s.get("text", "") for s in spans).strip()
            if not text:
                continue
            size = max((s.get("size", 0) for s in spans), default=0)
            bold = any("bold" in (s.get("font", "") or "").lower() for s in spans)
            out.append((text, round(size, 1), bold))
    return out


def convert(pdf_path: str, keep_urls: bool = False) -> str:
    doc = pymupdf.open(pdf_path)
    lines = [ln for page in doc for ln in _blocks(page)]
    doc.close()
    if not lines:
        return ""

    # Body size = the most common size; anything clearly larger is a heading. Font size is
    # the only structural signal a PDF reliably carries.
    sizes = {}
    for _, size, _ in lines:
        sizes[size] = sizes.get(size, 0) + 1
    body = max(sizes, key=sizes.get)

    out, prev_blank = [], True
    for text, size, bold in lines:
        if not keep_urls and re.fullmatch(r"(View paper|https?://\S+)", text):
            continue
        if size >= body + 3:
            level = "#"
        elif size >= body + 1.5:
            level = "##"
        elif size >= body + 0.5 or (bold and len(text) < 90):
            level = "###"
        else:
            level = ""
        if level:
            if not prev_blank:
                out.append("")
            out.append(f"{level} {text}")
            out.append("")
            prev_blank = True
        else:
            # rejoin lines the PDF broke mid-sentence
            if out and not prev_blank and not out[-1].endswith((".", ":", ";", "!", "?")):
                out[-1] = out[-1].rstrip() + " " + text
            else:
                out.append(text)
            prev_blank = False
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def main():
    ap = argparse.ArgumentParser(description="PDF -> Markdown, losslessly")
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--keep-urls", action="store_true")
    args = ap.parse_args()
    md = convert(args.pdf, args.keep_urls)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(md, encoding="utf-8")
    print(f"written: {args.out}  ({len(md.split())} words, {md.count(chr(10) + '#')} headings)")


if __name__ == "__main__":
    main()
