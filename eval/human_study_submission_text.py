"""Freeze one submission text per paper with the MinerU parser and check it."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DR = REPO / "DeepReviewer-v2"
OUT_DIR = REPO / "eval" / "out" / "human_study" / "submission_text"

sys.path.insert(0, str(REPO / "eval"))


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
        "has_references": bool(
            re.search(r"^#{1,4}\s*(references|bibliography)\b", text, re.M | re.I)
        ),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


MAIN_CONFIG = "final_evaluation/config/main.yaml"
MAIN_SOURCES = "final_evaluation/config/sources.main.yaml"


def papers(config: str = MAIN_CONFIG, sources: str = MAIN_SOURCES) -> dict:
    """{paper_key: submission pdf} from the sources config of the study or of the E1-only papers."""
    import yaml

    cfg = yaml.safe_load((REPO / config).read_text(encoding="utf-8"))
    src = yaml.safe_load((REPO / sources).read_text(encoding="utf-8"))
    return {k: REPO / src[k]["submission"]["pdf"] for k in cfg["papers"]}


def _adapter():
    """DeepReviewer's MinerU client, built inside DeepReviewer-v2 so that its .env is read."""
    cwd = Path.cwd()
    sys.path.insert(0, str(DR))
    os.chdir(DR)
    try:
        from deepreview.config import get_settings
        from deepreview.adapters.mineru import MineruAdapter, MineruConfig

        st = get_settings()
        ad = MineruAdapter(
            MineruConfig(
                base_url=st.mineru_base_url,
                api_token=st.mineru_api_token,
                model_version=st.mineru_model_version,
                upload_endpoint=st.mineru_upload_endpoint,
                poll_endpoint_templates=st.mineru_poll_templates(),
                poll_interval_seconds=st.mineru_poll_interval_seconds,
                poll_timeout_seconds=st.mineru_poll_timeout_seconds,
                allow_local_fallback=False,
            )
        )
    finally:
        os.chdir(cwd)
    if not ad.configured:
        raise SystemExit(
            "MinerU is not configured (MINERU_API_TOKEN / MINERU_BASE_URL "
            "in DeepReviewer-v2/.env). The local pypdf fallback is not used."
        )
    return ad


async def one(ad, key: str, pdf: Path) -> dict:
    res = await ad.parse_pdf(pdf_path=pdf, data_id=f"human_study__{key}")
    return {
        "markdown": res.markdown,
        "provider": res.provider,
        "batch_id": res.batch_id,
        "warning": res.warning,
        "content_list": res.content_list,
    }


async def run(sel: dict, write: bool) -> int:
    ad = _adapter()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failed = []
    for i, (key, pdf) in enumerate(sel.items(), 1):
        print(f"\n=== [{i}/{len(sel)}] {key} ===", flush=True)
        if not pdf.is_file():
            print(f"  PDF MISSING: {pdf}")
            failed.append(key)
            continue
        try:
            r = await one(ad, key, pdf)
        except Exception as exc:
            print(f"  FAILED: {type(exc).__name__}: {str(exc)[:200]}")
            failed.append(key)
            continue
        text, st = r["markdown"], stats(r["markdown"])
        print(f"  source     : {pdf.relative_to(REPO).as_posix()}")
        print(
            f"  provider   : {r['provider']}"
            + (f"  WARNING: {r['warning']}" if r["warning"] else "")
        )
        print(f"  size       : {st['chars']:,} chars, {st['words']:,} words, {st['lines']:,} lines")
        print(f"  math       : {st['display_math']} display, {st['inline_math']} inline")
        print(f"  tables     : {st['table_rows']} markdown rows, {st['html_tables']} html")
        print(
            f"  structure  : {st['headings']} headings, {st['images']} figures, "
            f"references section: {st['has_references']}"
        )
        print(f"  sha256     : {st['sha256'][:16]}...")
        print(f"  tail       : ...{' '.join(text.split()[-14:])}")
        if write:
            (OUT_DIR / f"{key}__submission.txt").write_text(text, encoding="utf-8")
            (OUT_DIR / f"{key}__submission.meta.json").write_text(
                json.dumps(
                    {
                        "paper": key,
                        "pdf": pdf.relative_to(REPO).as_posix(),
                        "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                        "provider": r["provider"],
                        "batch_id": r["batch_id"],
                        "warning": r["warning"],
                        **{k: v for k, v in st.items()},
                    },
                    ensure_ascii=False,
                    indent=1,
                ),
                encoding="utf-8",
            )
            print(
                f"  written    : {(OUT_DIR / f'{key}__submission.txt').relative_to(REPO).as_posix()}"
            )
    if failed:
        print(f"\nFAILED: {', '.join(failed)}")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--write", action="store_true", help="freeze the texts (default: check only)")
    ap.add_argument("--check", action="store_true", help="parse and report, write nothing")
    ap.add_argument("--only", default="", help="comma-separated paper keys")
    ap.add_argument("--config", default=MAIN_CONFIG, help="study config naming the papers")
    ap.add_argument("--sources", default=MAIN_SOURCES, help="its sources file")
    args = ap.parse_args()
    sel = papers(args.config, args.sources)
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        sel = {k: v for k, v in sel.items() if k in want}
        if not sel:
            print(f"no paper matched --only {args.only}")
            return 1
    if not (args.write or args.check):
        ap.error("--write or --check")
    return asyncio.run(run(sel, args.write))


if __name__ == "__main__":
    raise SystemExit(main())
