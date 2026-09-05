#!/usr/bin/env python3
"""
Freeze everything the pipeline renders from existing artifacts, so a refactor can be
proved to have changed nothing.

Three modules turn Artifact A and B into what a reader sees, and all three consult the
same rule about which prior work counts as overlapping a claim: the battle export, the
evidence block the synthesis reads, and the review-summary endpoint. This renders all
three for every submission in data/ that has a complete artifact set -- no model calls, no
network, no cost, because every input is already on disk.

Use it around any change that is supposed to be behaviour-preserving:

    python eval/render_snapshot.py --out .snapshots/before
    ...make the change...
    python eval/render_snapshot.py --out .snapshots/after --compare .snapshots/before

A refactor that claims to change nothing and prints one differing file is a refactor that
changed something. Note the converse limit: this proves the RENDERERS agree, not that a
rerun of the pipeline would produce the same artifacts -- the model is not involved here.
"""
import argparse
import filecmp
import glob
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src" / "novelty_assessment"))


def _complete_submissions(data_dir: Path):
    ids = []
    for f in sorted(glob.glob(str(data_dir / "*" / "*_artifact_a.json"))):
        d = Path(f).parent
        sid = d.name
        if (d / f"{sid}_artifact_b.json").exists() and (d / f"{sid}_claims.json").exists():
            ids.append(sid)
    return ids


def write(out_dir: Path, data_dir: Path) -> int:
    import battle_export
    from artifact_b import ArtifactBBuilder

    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    ids = _complete_submissions(data_dir)
    for sid in ids:
        for variant in ("", "linear"):
            tail = f"_{variant}" if variant else ""
            if not (data_dir / sid / f"{sid}_artifact_a{tail}.json").exists():
                continue
            try:
                md = battle_export.build(str(data_dir), sid, variant)
            except Exception as e:                       # keep going: one broken artifact
                md = f"[ERROR] {type(e).__name__}: {e}"  # must not hide the other 30
            (out_dir / f"export__{sid}{tail}.md").write_text(md, encoding="utf-8")

            a = json.loads((data_dir / sid / f"{sid}_artifact_a{tail}.json")
                           .read_text(encoding="utf-8"))
            try:
                ev = ArtifactBBuilder._format_evidence(a)
            except Exception as e:
                ev = f"[ERROR] {type(e).__name__}: {e}"
            (out_dir / f"evidence__{sid}{tail}.txt").write_text(ev, encoding="utf-8")
            n += 2

    # imported last: this pulls in FastAPI and builds the whole app
    try:
        import api
        for sid in ids:
            try:
                res = api.review_summary(sid)
            except Exception as e:
                res = {"ERROR": f"{type(e).__name__}: {e}"}
            (out_dir / f"summary__{sid}.json").write_text(
                json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            n += 1
    except Exception as e:
        (out_dir / "_api_import_failed.txt").write_text(
            f"{type(e).__name__}: {e}", encoding="utf-8")
    return n


def compare(new: Path, old: Path) -> int:
    a = {p.name for p in old.iterdir() if p.is_file()}
    b = {p.name for p in new.iterdir() if p.is_file()}
    problems = []
    for name in sorted(a - b):
        problems.append(f"  missing now: {name}")
    for name in sorted(b - a):
        problems.append(f"  new file   : {name}")
    for name in sorted(a & b):
        if not filecmp.cmp(old / name, new / name, shallow=False):
            problems.append(f"  DIFFERS    : {name}")
    if problems:
        print(f"\n{len(problems)} difference(s) against {old}:")
        print("\n".join(problems[:40]))
        if len(problems) > 40:
            print(f"  ... and {len(problems) - 40} more")
        return 1
    print(f"\nidentical to {old}: {len(a)} files, byte for byte")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Snapshot every rendered output")
    ap.add_argument("--out", required=True, help="directory to write the snapshot into")
    ap.add_argument("--data-dir", default=str(REPO / "data"))
    ap.add_argument("--compare", default="", help="an earlier snapshot to diff against")
    args = ap.parse_args()

    os.chdir(REPO)                       # the renderers resolve data/ relative to the repo
    out = Path(args.out)
    n = write(out, Path(args.data_dir))
    print(f"{n} rendered outputs -> {out}")
    if args.compare:
        raise SystemExit(compare(out, Path(args.compare)))


if __name__ == "__main__":
    main()
