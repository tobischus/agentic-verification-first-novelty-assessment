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
import os
import re
from collections import Counter
from pathlib import Path

# Cut at the PDF's own outline where it has one. Set to 0 to force the font heuristic,
# which is what a run before this change used.
_USE_OUTLINE = os.getenv("NOVELTY_PDF_OUTLINE", "1").strip().lower() not in ("0", "false", "no")

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


def _page_lines_geom(page):
    """Yield (bbox, text, max_font_size, bold_fraction) per visual line of a page."""
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
            yield line["bbox"], text, (max(sizes) if sizes else 0.0), bold_chars / n


def _page_lines(page):
    """Yield (text, max_font_size, bold_fraction) per visual line of a page."""
    for _bbox, text, size, bold in _page_lines_geom(page):
        yield text, size, bold


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


# --------------------------------------------------------------------------- #
# Sections from the PDF's own outline
#
# A LaTeX paper carries its structure with it: hyperref writes the real \section
# commands into the PDF as bookmarks, each with a destination -- the point the
# viewer jumps to when you click it. That is not heading DETECTION, it is what the
# author declared, so where it exists it beats reading font sizes off the page.
#
# Measured over the 170 unique related-work PDFs in the repo: 107 (63%) carry a
# usable outline, and 88% of this evaluation's own pool does. Cutting at the
# destination lands within one line of the declared heading for 942 of 1008
# top-level entries (93,5%); 88 of the 107 papers are flawless.
#
# The remaining failures cluster by typesetting class rather than scattering --
# some IEEE templates place every destination a heading too early -- so the gate
# below is per paper, not per entry: if the text at the anchors does not
# corroborate the declared titles, the whole paper falls back to the heuristic.
# --------------------------------------------------------------------------- #

_OUTLINE_MAX_LEVEL = 2      # deeper entries merge into their parent section
_ANCHOR_TOL = 3.0           # pt: the destination sits just above its heading
_ANCHOR_MIN_OK = 0.5        # share of anchors that must corroborate their title
# Section numbering in any of the shapes papers use: "3", "3.1", "IV.", "A.", "B.2",
# and the bare appendix letter that precedes a capitalised title ("B More Results").
_HEAD_NUM = re.compile(r"^\s*(?:\d+(?:\.\d+)*[.)]?|[A-Z]\.?\d+(?:\.\d+)*[.)]?"
                       r"|[IVXLC]+[.)]|[A-Z][.)]?(?=\s+[A-Z]))\s+")


def _norm_head(t: str) -> str:
    """Compare headings on their words alone; numbering and case are convention.

    The numbering has to go because the two sides carry different ones: the bookmark
    says "Introduction" where the page is set "I. INTRODUCTION", and an appendix
    letter often lives only in the bookmark. Stripped repeatedly, since the forms
    stack ("2 A Holistic Framework" against "A Holistic Framework")."""
    s = (t or "").strip()
    for _ in range(3):
        nxt = _HEAD_NUM.sub("", s, count=1)
        if nxt == s:
            break
        s = nxt
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _undouble(t: str) -> str:
    """'Knowledge Graph Knowledge Graph' -> 'Knowledge Graph'.

    hyperref writes the title twice when a \\section carries a separate running
    head; left alone, the doubled form matches nothing on the page."""
    s = (t or "").strip()
    h = len(s) // 2
    if len(s) > 6 and s[:h].strip().lower() == s[h:].strip().lower():
        return s[:h].strip()
    return s


def _reading_key(pno: int, x0: float, y0: float, width: float):
    """Sort key putting lines in reading order: page, then column, then height.

    The column split is the page midpoint. Two-column papers set their right
    column near x=318 of 612, single-column text starts far left and never
    crosses it, so the same rule serves both without detecting the layout."""
    return (pno, 0 if x0 < width / 2 else 1, y0)


def _outline_marks(doc, max_level: int = _OUTLINE_MAX_LEVEL):
    """[(key, path_title, leaf_title)] for the outline entries worth cutting at.

    `path_title` carries the ancestors ('Knowledge Graph > Retriever'). Without it
    a survey that gives every chapter the same sub-structure ends up with seven
    sections called 'Retriever', and get_sections -- which joins chunks by NAME --
    hands back all seven as one block."""
    try:
        toc = doc.get_toc(False) or []
    except Exception:
        return [], 0
    marks, path, n_top, n_dest = [], {}, 0, 0
    for entry in toc:
        try:
            lvl, title, _pg, dest = entry[0], entry[1], entry[2], entry[3]
        except (IndexError, TypeError):
            continue
        leaf = _undouble(title)
        if not leaf:
            continue
        path[lvl] = leaf
        for deeper in [k for k in path if k > lvl]:
            path.pop(deeper, None)
        if lvl == 1:
            n_top += 1
        if lvl > max_level or not isinstance(dest, dict) or dest.get("to") is None:
            continue
        pno = dest.get("page")
        if pno is None or not (0 <= pno < doc.page_count):
            continue
        n_dest += 1
        page = doc[pno]
        pt = dest["to"]
        # PDF coordinates start at the bottom of the page; the text does not.
        ytop = page.rect.height - pt.y
        marks.append((_reading_key(pno, pt.x, ytop, page.rect.width),
                      " > ".join(path[k] for k in sorted(path)), leaf))
    marks.sort(key=lambda m: m[0])
    return marks, n_top


def _sections_from_outline(doc, seq):
    """[(title, [line, ...])] cut at the outline's anchors, or None to fall back.

    `seq` is [(reading_key, text)] for the whole document. Every line lands in a
    section -- what precedes the first anchor becomes front matter -- because this
    text is also the corpus every quote is verified against, and a splitter that
    drops lines makes previously verified quotes fail."""
    marks, n_top = _outline_marks(doc)
    if n_top < 3 or len(marks) < 3:
        return None

    # Does the text at each anchor corroborate the title the outline declares?
    # Checked in a window, because the anchor sits above its heading and the
    # heading itself is often set as two lines ('3' and 'METHOD').
    ok = 0
    for key, _path, leaf in marks:
        i = next((j for j, (k, _t) in enumerate(seq)
                  if k >= (key[0], key[1], key[2] - _ANCHOR_TOL)), None)
        if i is None:
            continue
        window = _norm_head(" ".join(t for _k, t in seq[max(0, i - 1): i + 3]))
        n = _norm_head(leaf)
        if n and (n in window or (len(n) > 8 and n[: len(n) * 2 // 3] in window)):
            ok += 1
    if ok < _ANCHOR_MIN_OK * len(marks):
        return None                      # destinations systematically off

    bounds = []
    for key, path_title, leaf in marks:
        i = next((j for j, (k, _t) in enumerate(seq)
                  if k >= (key[0], key[1], key[2] - _ANCHOR_TOL)), None)
        if i is not None:
            bounds.append((i, path_title, leaf))
    if not bounds:
        return None

    sections = []
    if bounds[0][0] > 0:
        sections.append(("", [t for _k, t in seq[: bounds[0][0]]]))
    for n, (i, path_title, leaf) in enumerate(bounds):
        j = bounds[n + 1][0] if n + 1 < len(bounds) else len(seq)
        body = [t for _k, t in seq[i:j]]
        # Drop the heading's own line(s) from the body: the title is the section's
        # name already, and leaving it in front of the text reads as a duplicate.
        while body and len(body[0]) < 90 and _norm_head(body[0]) \
                and _norm_head(body[0]) in _norm_head(leaf):
            body.pop(0)
        sections.append((path_title, body))
    return sections


def _render(sections) -> str:
    """[(heading, [line, ...])] -> the '## Section\\ntext' dump both paths return.

    The bibliography and acknowledgments are dropped here rather than in either
    splitter, so the two agree on it: a quote must never be verifiable against a
    reference list, and that has to hold however the sections were found."""
    out = []
    for head, lines in sections:
        leaf = (head or "").split(" > ")[-1].strip()
        if leaf and _DROP_SECTIONS.match(leaf):
            continue  # never feed the bibliography/acknowledgments to the agent
        txt = _clean("\n".join(lines))
        if not txt:
            continue
        if head:
            out.append(f"## {head}\n{txt}")
        else:
            out.append(f"## Front matter (title & abstract)\n{txt}")
    return "\n\n".join(out)


def pdf_to_sectioned_text(pdf_path) -> str:
    """Parse a PDF into '## Section\\ntext' full text (grobid-dump compatible).

    Returns "" if the PDF has no extractable text (e.g. scanned images)."""
    import fitz  # pymupdf

    doc = fitz.open(str(pdf_path))
    try:
        all_lines = []  # (page_no, text, size, bold)
        seq = []        # (reading_key, text) -- for the outline splitter
        for pno, page in enumerate(doc):
            w = page.rect.width
            for bbox, text, size, bold in _page_lines_geom(page):
                all_lines.append((pno, text, size, bold))
                seq.append((_reading_key(pno, bbox[0], bbox[1], w), text))
        if not all_lines:
            return ""
        seq.sort(key=lambda e: e[0])
        # The paper's own declared structure first; font heuristics only where the
        # PDF does not carry one, or where its destinations do not hold up.
        # NOVELTY_PDF_OUTLINE=0 forces the old path, so a run can be compared against
        # the sectioning it used to have without checking out an older revision.
        outline = _sections_from_outline(doc, seq) if _USE_OUTLINE else None
    finally:
        doc.close()

    if outline is not None:
        return _render([[head, lines] for head, lines in outline])

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

    return _render(sections)


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
