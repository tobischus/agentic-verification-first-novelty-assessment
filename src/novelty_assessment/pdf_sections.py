"""Sectioned full text of a prior paper, parsed with PyMuPDF.

Sections are cut at the PDF outline when it is reliable, otherwise at headings detected
from font size, weight and numbering. The output has the form "## Section\ntext" and is
both what the agent reads and the text every quote is verified against.
"""

import re
from collections import Counter

_DROP_SECTIONS = re.compile(r"^(references?|bibliography|acknowledg\w*)\b", re.I)
_CAPTION = re.compile(r"^(figure|fig\.?|table|tab\.?|listing|algorithm)\s*\d", re.I)
_NUMBERED = re.compile(r"^([A-Z]?\d+(\.\d+)*|[IVX]+)[.)]?\s+\S")
_IEEE_NUM = re.compile(r"^([IVX]+|\d+(\.\d+)*|[A-Z])[.)]\s+(\S.*)$")

_OUTLINE_MAX_LEVEL = 2
_ANCHOR_TOL = 3.0
_ANCHOR_MIN_OK = 0.5
_HEAD_NUM = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*[.)]?|[A-Z]\.?\d+(?:\.\d+)*[.)]?"
    r"|[IVXLC]+[.)]|[A-Z][.)]?(?=\s+[A-Z]))\s+"
)


def _clean(text: str) -> str:
    """Join hyphenated line breaks and collapse whitespace."""
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def _page_lines_geom(page):
    """Yield (bbox, text, max_font_size, bold_fraction) for each horizontal text line."""
    d = page.get_text("dict")
    for block in d.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
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


def _body_size(lines) -> float:
    """Dominant font size, weighted by characters and rounded to 0.5 pt."""
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
    # Headings set in body size without bold, e.g. "I. INTRODUCTION".
    m = _IEEE_NUM.match(text)
    if m:
        rest = m.group(3)
        if (
            len(text) < 80
            and "," not in rest
            and len(rest.split()) <= 8
            and (rest.isupper() or rest[:1].isupper())
            and not rest.rstrip().endswith(".")
        ):
            return True
    return False


def _norm_head(t: str) -> str:
    """Heading reduced to lowercase alphanumerics, without leading section numbers."""
    s = (t or "").strip()
    for _ in range(3):
        nxt = _HEAD_NUM.sub("", s, count=1)
        if nxt == s:
            break
        s = nxt
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _undouble(t: str) -> str:
    """Collapse a title that the outline repeats, e.g. 'Graph Graph' -> 'Graph'."""
    s = (t or "").strip()
    h = len(s) // 2
    if len(s) > 6 and s[:h].strip().lower() == s[h:].strip().lower():
        return s[:h].strip()
    return s


def _reading_key(pno: int, x0: float, y0: float, width: float):
    """Sort key for reading order: page, column (split at the page midpoint), height."""
    return (pno, 0 if x0 < width / 2 else 1, y0)


def _outline_marks(doc, max_level: int = _OUTLINE_MAX_LEVEL):
    """Outline entries as (reading_key, path_title, leaf_title), plus the top-level count."""
    try:
        toc = doc.get_toc(False) or []
    except Exception:
        return [], 0
    marks, path, n_top = [], {}, 0
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
        page = doc[pno]
        pt = dest["to"]
        ytop = page.rect.height - pt.y
        marks.append(
            (
                _reading_key(pno, pt.x, ytop, page.rect.width),
                " > ".join(path[k] for k in sorted(path)),
                leaf,
            )
        )
    marks.sort(key=lambda m: m[0])
    return marks, n_top


def _sections_from_outline(doc, seq):
    """Sections cut at the outline destinations, or None if the outline is unreliable.

    The outline is accepted if it has at least three top-level entries and the text at
    the destinations matches at least half of the titles. Every line is assigned to a
    section, since the result is also the text that quotes are verified against.
    """
    marks, n_top = _outline_marks(doc)
    if n_top < 3 or len(marks) < 3:
        return None

    ok = 0
    for key, _path, leaf in marks:
        i = next(
            (j for j, (k, _t) in enumerate(seq) if k >= (key[0], key[1], key[2] - _ANCHOR_TOL)),
            None,
        )
        if i is None:
            continue
        window = _norm_head(" ".join(t for _k, t in seq[max(0, i - 1) : i + 3]))
        n = _norm_head(leaf)
        if n and (n in window or (len(n) > 8 and n[: len(n) * 2 // 3] in window)):
            ok += 1
    if ok < _ANCHOR_MIN_OK * len(marks):
        return None

    bounds = []
    for key, path_title, leaf in marks:
        i = next(
            (j for j, (k, _t) in enumerate(seq) if k >= (key[0], key[1], key[2] - _ANCHOR_TOL)),
            None,
        )
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
        while (
            body
            and len(body[0]) < 90
            and _norm_head(body[0])
            and _norm_head(body[0]) in _norm_head(leaf)
        ):
            body.pop(0)
        sections.append((path_title, body))
    return sections


def _render(sections) -> str:
    """Render sections as '## Section\\ntext', without references and acknowledgements."""
    out = []
    for head, lines in sections:
        leaf = (head or "").split(" > ")[-1].strip()
        if leaf and _DROP_SECTIONS.match(leaf):
            continue
        txt = _clean("\n".join(lines))
        if not txt:
            continue
        if head:
            out.append(f"## {head}\n{txt}")
        else:
            out.append(f"## Front matter (title & abstract)\n{txt}")
    return "\n\n".join(out)


def pdf_to_sectioned_text(pdf_path) -> str:
    """Parse a PDF into sectioned full text. Returns "" if the PDF has no text layer."""
    import fitz

    doc = fitz.open(str(pdf_path))
    try:
        all_lines = []
        seq = []
        for pno, page in enumerate(doc):
            w = page.rect.width
            for bbox, text, size, bold in _page_lines_geom(page):
                all_lines.append((pno, text, size, bold))
                seq.append((_reading_key(pno, bbox[0], bbox[1], w), text))
        if not all_lines:
            return ""
        seq.sort(key=lambda e: e[0])
        outline = _sections_from_outline(doc, seq)
    finally:
        doc.close()

    if outline is not None:
        return _render([[head, lines] for head, lines in outline])

    body = _body_size([(t, s, b) for _, t, s, b in all_lines])
    sections = []
    current = ["", []]
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
        # No usable headings: split into sections of two pages each.
        per_page = {}
        for pno, text, _, _ in all_lines:
            per_page.setdefault(pno, []).append(text)
        pages = sorted(per_page)
        out, step = [], 2
        for i in range(0, len(pages), step):
            chunk_pages = pages[i : i + step]
            txt = _clean("\n".join("\n".join(per_page[p]) for p in chunk_pages))
            if txt:
                label = (
                    f"Pages {chunk_pages[0] + 1}-{chunk_pages[-1] + 1}"
                    if len(chunk_pages) > 1
                    else f"Page {chunk_pages[0] + 1}"
                )
                out.append(f"## {label}\n{txt}")
        return "\n\n".join(out)

    return _render(sections)
