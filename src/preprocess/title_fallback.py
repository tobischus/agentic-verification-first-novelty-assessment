#!/usr/bin/env python3
"""
Title recovery / cleaning for the document-processing stage.

GROBID's header model frequently fails on venue-watermarked submission PDFs
(e.g. ICLR "Under review as a conference paper at ...") -- it either returns an
empty title or prepends the watermark. Since the evaluation corpus is entirely
such submissions, a robust fallback is required.

Two cheap, layered remedies:
  1. clean_title(): deterministic regex strip of common venue watermarks. No LLM.
  2. recover_title(): when the title is empty/too short, extract page-1 text via
     PyMuPDF and have a small LLM call return the clean title. Robust against
     small-caps span splitting, margin line-numbers, and watermarks.

The recovered title should be surfaced to the reviewer for confirmation in the
human-in-the-loop step (it is metadata, not a novelty judgment).
"""
import re

# Common venue watermark prefixes that pollute extracted titles.
_WATERMARK_PATTERNS = [
    r"^\s*under review as a conference paper at .*?\d{4}\s*",
    r"^\s*published as a conference paper at .*?\d{4}\s*",
    r"^\s*accepted (as )?.*?conference.*?\d{4}\s*",
    r"^\s*preprint\.?\s*under review\.?\s*",
    r"^\s*under review\.?\s*",
]


def clean_title(title: str) -> str:
    """Strip leading venue-watermark phrases from a title. Deterministic, no LLM."""
    if not title:
        return ""
    t = title.strip()
    changed = True
    while changed:
        changed = False
        for pat in _WATERMARK_PATTERNS:
            m = re.match(pat, t, flags=re.IGNORECASE)
            if m and m.end() > 0:
                t = t[m.end():].strip()
                changed = True
    return t.strip()


def page1_text(pdf_path: str, max_chars: int = 2500) -> str:
    """Extract first-page text via PyMuPDF, dropping pure line-number lines."""
    import fitz  # pymupdf

    doc = fitz.open(pdf_path)
    if doc.page_count == 0:
        return ""
    raw = doc[0].get_text("text")
    lines = [
        ln
        for ln in raw.splitlines()
        if ln.strip() and not re.fullmatch(r"\d{1,4}", ln.strip())
    ]
    return "\n".join(lines)[:max_chars]


def recover_title(pdf_path: str, model: str = "gpt-4.1") -> str:
    """Recover the paper title from page-1 text via a small LLM call."""
    from langchain_openai import ChatOpenAI

    text = page1_text(pdf_path)
    if not text:
        return ""
    llm = ChatOpenAI(model_name=model, temperature=0.0)
    prompt = (
        "Below is the raw extracted text of the FIRST PAGE of a scientific paper. "
        "It may contain margin line-numbers, a venue watermark (e.g. 'Under review "
        "as a conference paper at ICLR 2025'), author names, and the abstract.\n\n"
        "Return ONLY the paper's title in correct title casing. No quotes, no venue "
        "or watermark text, no authors, nothing else.\n\n"
        "FIRST PAGE TEXT:\n" + text
    )
    resp = llm.invoke(prompt)
    return resp.content.strip().strip('"').strip()


def resolve_title(raw_title: str, pdf_path: str, model: str = "gpt-4.1",
                  min_len: int = 8):
    """
    Return (title, source) where source is one of:
      'grobid'            -> GROBID title used as-is
      'grobid_cleaned'    -> GROBID title after watermark strip
      'pdf_llm_fallback'  -> recovered from page-1 text via LLM
    """
    raw = (raw_title or "").strip()
    cleaned = clean_title(raw)
    if cleaned and len(cleaned) >= min_len:
        return cleaned, ("grobid" if cleaned == raw else "grobid_cleaned")
    recovered = recover_title(pdf_path, model=model)
    return recovered, "pdf_llm_fallback"
