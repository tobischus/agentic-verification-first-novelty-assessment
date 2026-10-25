"""Inputs for Afzal et al.'s assessment stage, built from this pipeline's outputs."""
import argparse
import json
import re
from pathlib import Path

_INTRO_TITLE = re.compile(r"^\s*(?:[IVX0-9]+[.\s)]*)?(introduction|background)\b", re.I)


def _from_sections(sections, max_chars: int) -> str:
    """Text of the first introduction-like section, else of the first section."""
    for sec in sections or []:
        if _INTRO_TITLE.match((sec.get("section") or "").strip()):
            text = (sec.get("text") or "").strip()
            if text:
                return text[:max_chars]
    for sec in sections or []:
        text = (sec.get("text") or "").strip()
        if text:
            return text[:max_chars]
    return ""


def _from_markdown(text: str, max_chars: int) -> str:
    """Introduction from a GROBID text with '## Heading' sections."""
    blocks = re.split(r"^##\s*(.+)$", text, flags=re.M)
    for i in range(1, len(blocks) - 1, 2):
        if _INTRO_TITLE.match(blocks[i].strip()):
            body = blocks[i + 1].strip()
            if body:
                return body[:max_chars]
    for i in range(1, len(blocks) - 1, 2):
        if not blocks[i].strip().lower().startswith("abstract"):
            body = blocks[i + 1].strip()
            if body:
                return body[:max_chars]
    return text[:max_chars]


def build(data_dir: str, submission_id: str, max_chars: int = 20000) -> dict:
    sub = Path(data_dir) / submission_id
    out_dir = sub / "introductions"
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = {"submission": False, "papers_written": 0, "papers_missing_fulltext": 0}

    ft = sub / f"{submission_id}_fulltext.json"
    if ft.exists():
        intro = _from_sections(json.loads(ft.read_text(encoding="utf-8")).get("sections"), max_chars)
        if intro:
            (out_dir / f"{submission_id}_intro.txt").write_text(intro, encoding="utf-8")
            stats["submission"] = True

    ranked = sub / "related_work_data" / "ranked_papers.json"
    for p in (json.loads(ranked.read_text(encoding="utf-8")) if ranked.exists() else []):
        pid = p.get("paper_id")
        if not pid:
            continue
        src = sub / "related_work_data" / "grobid_fulltext" / f"{pid}.txt"
        if not src.exists():
            stats["papers_missing_fulltext"] += 1
            continue
        intro = _from_markdown(src.read_text(encoding="utf-8", errors="ignore"), max_chars)
        if intro:
            (out_dir / f"{pid}_intro.txt").write_text(intro, encoding="utf-8")
            stats["papers_written"] += 1
    return stats


def main():
    ap = argparse.ArgumentParser(description="Write introductions/ for Afzal et al.'s pipeline")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--submission-id", required=True)
    ap.add_argument("--max-chars", type=int, default=20000)
    args = ap.parse_args()
    s = build(args.data_dir, args.submission_id, args.max_chars)
    print(f"submission intro written: {s['submission']}")
    print(f"related-paper intros    : {s['papers_written']} "
          f"({s['papers_missing_fulltext']} pool papers have no parsed full text)")


if __name__ == "__main__":
    main()
