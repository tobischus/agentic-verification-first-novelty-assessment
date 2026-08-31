#!/usr/bin/env python3
"""Side-by-side comparison of the two related-work full-text parsers:

    PyMuPDF (in-process, pdf_sections.py -- what the pipeline uses now)
    vs. GROBID (the external service it replaced)

For a few PDFs it runs BOTH, reports #sections / #chars / time and the section-title
overlap, and dumps each parser's full sectioned output to a file so you can open them
and judge quality yourself (is the section structure right? is the body text clean?).

Run (needs GROBID up for the GROBID side):
    python eval/compare_parsers.py --n 3
    python eval/compare_parsers.py --pdfs "data/<run>/related_work_data/pdfs" --n 5
Outputs land in eval/parser_compare/.
"""
import argparse
import glob
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src" / "novelty_assessment"))
sys.path.insert(0, str(_REPO / "src" / "preprocess"))

from rapidfuzz import fuzz


def parse_pymupdf_dump(text: str):
    """'## Title\\ntext' dump -> [{section, text}]."""
    secs, cur = [], None
    for line in text.split("\n"):
        if line.startswith("## "):
            if cur:
                secs.append(cur)
            cur = {"section": line[3:].strip(), "text": ""}
        elif cur is not None:
            cur["text"] += line + "\n"
    if cur:
        secs.append(cur)
    return [{"section": s["section"], "text": s["text"].strip()} for s in secs]


def pymupdf_sections(pdf: Path):
    from pdf_sections import pdf_to_sectioned_text
    t0 = time.time()
    dump = pdf_to_sectioned_text(pdf)
    return parse_pymupdf_dump(dump), round(time.time() - t0, 1)


def grobid_sections(pdf: Path, server: str):
    from grobid_client import GrobidClient
    from extract_metadata import EnhancedGrobidParser
    from lxml import etree
    t0 = time.time()
    tei = GrobidClient(server).pdf_to_tei(str(pdf))
    root = etree.fromstring(tei.encode("utf-8"))
    secs = EnhancedGrobidParser().extract_full_text_sections(root)
    secs = [{"section": (s.get("section") or "").strip(), "text": (s.get("text") or "").strip()} for s in secs]
    return secs, round(time.time() - t0, 1)


def title_overlap(a_secs, b_secs) -> float:
    """Fraction of GROBID section titles that have a close PyMuPDF counterpart."""
    at = [s["section"].lower() for s in a_secs if s["section"]]
    bt = [s["section"].lower() for s in b_secs if s["section"]]
    if not at:
        return 0.0
    hit = sum(1 for x in at if any(fuzz.ratio(x, y) >= 80 for y in bt))
    return round(hit / len(at), 2)


def dump_md(path: Path, parser: str, pdf_name: str, secs, secs_time):
    L = [f"# {parser} :: {pdf_name}",
         f"_{len(secs)} sections · {sum(len(s['text']) for s in secs):,} chars · {secs_time}s_\n"]
    for s in secs:
        L.append(f"## {s['section'] or '(untitled)'}  [{len(s['text']):,} chars]")
        L.append(s["text"] or "(empty)")
        L.append("")
    path.write_text("\n".join(L), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdfs", default=None, help="dir or glob of PDFs (default: newest run's related_work_data/pdfs)")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--grobid-server", default="http://localhost:8070")
    ap.add_argument("--out", default=str(_REPO / "eval" / "parser_compare"))
    args = ap.parse_args()

    if args.pdfs:
        pat = args.pdfs
        pdfs = sorted(glob.glob(str(Path(pat) / "*.pdf") if Path(pat).is_dir() else pat))
    else:
        dirs = sorted(glob.glob(str(_REPO / "data" / "*" / "related_work_data" / "pdfs")),
                      key=lambda p: Path(p).stat().st_mtime, reverse=True)
        pdfs = sorted(glob.glob(str(Path(dirs[0]) / "*.pdf"))) if dirs else []
    pdfs = [Path(p) for p in pdfs][: args.n]
    if not pdfs:
        print("No PDFs found. Pass --pdfs <dir>."); sys.exit(1)

    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    print(f"Comparing {len(pdfs)} PDFs. Dumps -> {out}\n")
    print(f"{'PDF':<20} | {'PyMuPDF sec/chars/s':<26} | {'GROBID sec/chars/s':<26} | title-overlap")
    print("-" * 100)

    rows = []
    for pdf in pdfs:
        stem = pdf.stem[:18]
        try:
            py, pyt = pymupdf_sections(pdf)
        except Exception as e:
            print(f"{stem:<20} | PyMuPDF ERROR: {repr(e)[:60]}"); continue
        try:
            gr, grt = grobid_sections(pdf, args.grobid_server)
        except Exception as e:
            print(f"{stem:<20} | GROBID ERROR: {repr(e)[:60]} (is GROBID up?)"); gr, grt = [], 0.0
        ov = title_overlap(gr, py) if gr else 0.0
        py_c = sum(len(s["text"]) for s in py)
        gr_c = sum(len(s["text"]) for s in gr)
        print(f"{stem:<20} | {f'{len(py)}/{py_c:,}/{pyt}s':<26} | {f'{len(gr)}/{gr_c:,}/{grt}s':<26} | {ov}")
        dump_md(out / f"{pdf.stem}.pymupdf.md", "PyMuPDF", pdf.name, py, pyt)
        if gr:
            dump_md(out / f"{pdf.stem}.grobid.md", "GROBID", pdf.name, gr, grt)
        rows.append((pdf.name, len(py), py_c, pyt, len(gr), gr_c, grt, ov))

    print("\nOpen the *.pymupdf.md / *.grobid.md pairs in eval/parser_compare/ to compare section")
    print("structure and body text quality. Rule of thumb: PyMuPDF is usable if the section")
    print("titles broadly match GROBID's and the body text is clean & complete.")


if __name__ == "__main__":
    main()
