"""Title recovery / cleaning for the document-processing stage."""
import re

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
    import fitz

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
    """(title, source) with source 'grobid', 'grobid_cleaned' or 'pdf_llm_fallback'."""
    raw = (raw_title or "").strip()
    cleaned = clean_title(raw)
    if cleaned and len(cleaned) >= min_len:
        return cleaned, ("grobid" if cleaned == raw else "grobid_cleaned")
    recovered = recover_title(pdf_path, model=model)
    return recovered, "pdf_llm_fallback"
