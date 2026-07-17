#!/usr/bin/env python3
"""
In-process PDF -> sectioned full text via PyMuPDF (no external service).

Replaces GROBID for RELATED-WORK full text (the submission keeps GROBID: its
structured metadata / citation contexts are needed there). The claim agent only
needs section titles + verbatim body text from candidate papers, and GROBID --
a Docker service that is slow and unstable on low-RAM machines -- is overkill
for that. PyMuPDF parses a paper in ~1s fully in-process.

Output format is EXACTLY the grobid_fulltext dump format ("## Section\\ntext"),
so everything downstream (passages.chunks_from_grobid_text, the agent's
section_menu / read_sections, quote verification) works unchanged. Verification
integrity is preserved by construction: quotes are verified against the parsed
text itself, not the original PDF, so parser noise cannot produce false ✓.

Heading detection is heuristic (font size / boldness / numbering patterns).
It works well on LaTeX-born papers (arXiv etc.); for PDFs where no headings
are detected, the text is split into page-range pseudo-sections so the agent's
section-selection mechanism still functions.
"""
import re
from collections import Counter
from pathlib import Path

# section titles whose CONTENT we drop (the agent must never quote from the
# bibliography, and acknowledgments are noise)
_DROP_SECTIONS = re.compile(r"^(references?|bibliography|acknowledg\w*)\b", re.I)
# lines that look like captions, not section headings
_CAPTION = re.compile(r"^(figure|fig\.?|table|tab\.?|listing|algorithm)\s*\d", re.I)
# numbered heading like "1 Introduction", "2.3 Method", "A.1 Details", "IV. Results"
_NUMBERED = re.compile(r"^([A-Z]?\d+(\.\d+)*|[IVX]+)[.)]?\s+\S")
# IEEE/ACM style: "I. INTRODUCTION", "A. Method" -- small-caps headings at BODY size,
# not bold, so font signals alone miss them entirely
_IEEE_NUM = re.compile(r"^([IVX]+|\d+(\.\d+)*|[A-Z])[.)]\s+(\S.*)$")


def _clean(text: str) -> str:
    """Join hyphenated line breaks and collapse whitespace inside a paragraph."""
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)   # hyphenation across lines
    text = re.sub(r"\s*\n\s*", " ", text)                 # soft line breaks -> spaces
    return re.sub(r"[ \t]+", " ", text).strip()


def _page_lines(page):
    """Yield (text, max_font_size, bold_fraction) per visual line of a page."""
    d = page.get_text("dict")
    for block in d.get("blocks", []):
        if block.get("type") != 0:  # text blocks only
            continue
        for line in block.get("lines", []):
            # skip rotated text (arXiv sidebar watermark is vertical)
            dx, dy = line.get("dir", (1, 0))
            if abs(dx) < 0.5:
                continue
            spans = line.get("spans", [])
            text = "".join(s.get("text", "") for s in spans).strip()
            if not text:
                continue
            sizes = [s.get("size", 0) for s in spans for _ in s.get("text", "")]
            bold_chars = sum(
                len(s.get("text", ""))
                for s in spans
                if (s.get("flags", 0) & 16) or "bold" in (s.get("font", "").lower())
            )
            n = sum(len(s.get("text", "")) for s in spans) or 1
            yield text, (max(sizes) if sizes else 0.0), bold_chars / n


def _body_size(lines) -> float:
    """The dominant (body) font size, char-weighted, rounded to 0.5pt."""
    counter = Counter()
    for text, size, _ in lines:
        counter[round(size * 2) / 2] += len(text)
    return counter.most_common(1)[0][0] if counter else 10.0


def _is_heading(text: str, size: float, bold: float, body: float) -> bool:
    if len(text) > 120 or len(re.findall(r"[A-Za-z]", text)) < 3:
        return False
    if _CAPTION.match(text):
        return False
    if text.rstrip().endswith((".", ",", ";", ":")) and not _NUMBERED.match(text):
        return False
    clearly_larger = size >= body + 0.8
    boldish = bold >= 0.7 and size >= body - 0.1
    if clearly_larger:
        return True
    if boldish and (_NUMBERED.match(text) or text.isupper() or len(text) < 60):
        return True
    # IEEE/ACM small-caps headings ("I. INTRODUCTION", "A. Method"): body size,
    # not bold -- accept on the strength of the numbering + heading-like shape alone
    m = _IEEE_NUM.match(text)
    if m:
        rest = m.group(3)
        if (len(text) < 80 and "," not in rest and len(rest.split()) <= 8
                and (rest.isupper() or rest[:1].isupper())
                and not rest.rstrip().endswith(".")):
            return True
    return False


def pdf_to_sectioned_text(pdf_path) -> str:
    """Parse a PDF into '## Section\\ntext' full text (grobid-dump compatible).

    Returns "" if the PDF has no extractable text (e.g. scanned images)."""
    import fitz  # pymupdf

    doc = fitz.open(str(pdf_path))
    try:
        all_lines = []  # (page_no, text, size, bold)
        for pno, page in enumerate(doc):
            for text, size, bold in _page_lines(page):
                all_lines.append((pno, text, size, bold))
    finally:
        doc.close()

    if not all_lines:
        return ""
    body = _body_size([(t, s, b) for _, t, s, b in all_lines])

    # assemble (heading, [lines...]) sections in document order
    sections = []           # [ [head, [line, ...]] ]
    current = ["", []]      # preamble (title/authors/abstract) has no heading
    for pno, text, size, bold in all_lines:
        if _is_heading(text, size, bold, body):
            if current[1] or current[0]:
                sections.append(current)
            current = [text, []]
        else:
            current[1].append(text)
    if current[1] or current[0]:
        sections.append(current)

    named = [s for s in sections if s[0]]
    if len(named) < 3:
        # heading detection failed for this PDF -> page-range pseudo-sections so the
        # agent's section-selection mechanism still has something to choose from
        per_page = {}
        for pno, text, _, _ in all_lines:
            per_page.setdefault(pno, []).append(text)
        pages = sorted(per_page)
        out, step = [], 2
        for i in range(0, len(pages), step):
            chunk_pages = pages[i:i + step]
            txt = _clean("\n".join("\n".join(per_page[p]) for p in chunk_pages))
            if txt:
                label = (f"Pages {chunk_pages[0] + 1}-{chunk_pages[-1] + 1}"
                         if len(chunk_pages) > 1 else f"Page {chunk_pages[0] + 1}")
                out.append(f"## {label}\n{txt}")
        return "\n\n".join(out)

    out = []
    for head, lines in sections:
        if head and _DROP_SECTIONS.match(head):
            continue  # never feed the bibliography/acknowledgments to the agent
        txt = _clean("\n".join(lines))
        if not txt:
            continue
        if head:
            out.append(f"## {head}\n{txt}")
        else:
            out.append(f"## Front matter (title & abstract)\n{txt}")
    return "\n\n".join(out)


if __name__ == "__main__":
    import sys
    import time

    for p in sys.argv[1:]:
        t0 = time.time()
        text = pdf_to_sectioned_text(p)
        heads = re.findall(r"^## (.+)$", text, re.M)
        print(f"{Path(p).name}: {len(text)} chars, {len(heads)} sections, {time.time()-t0:.2f}s")
        for h in heads[:12]:
            print(f"   - {h}")
