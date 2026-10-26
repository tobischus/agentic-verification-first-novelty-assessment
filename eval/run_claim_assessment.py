"""Claim explanations for the human-study papers, agent and linear. Backs up Artifact B first and records tokens, cost and time per report."""

import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, "src/novelty_assessment")
import claim_assessment as ca
from agent.claim_agent import _usd

MODEL = "gpt-5.6-luna"
OUT = Path("eval/out/human_study/claim_assessment")
keys = sorted(p.name for p in Path("final_evaluation/inputs/main").iterdir() if p.is_dir())
log = {
    "model": MODEL,
    "prompt_version": ca.PROMPT_VERSION,
    "prompt_sha256": ca.prompt_sha256(),
    "reports": [],
}
for key in keys:
    for v in ("agent", "linear"):
        src = Path("data") / key / f"{key}_artifact_b_{v}.json"
        bak = OUT / "artifact_b_before" / src.name
        if not bak.exists():
            shutil.copy2(src, bak)
        t = time.time()
        res = ca.build("data", key, v, model_name=MODEL)
        pt = sum(r["usage"]["prompt_tokens"] or 0 for r in res)
        ct = sum(r["usage"]["completion_tokens"] or 0 for r in res)
        row = {
            "paper": key,
            "variant": v,
            "claims": len(res),
            "seconds": round(time.time() - t, 1),
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "usd_upper_bound": _usd(MODEL, pt, ct),
            "revised": sum(r["revised_after_check"] for r in res),
            "open_problems": [p for r in res for p in r["open_check_problems"]],
            "words": [r["word_count"] for r in res],
        }
        log["reports"].append(row)
        print(
            f"{key[:30]:30s} {v:6s} {row['claims']} claims {row['seconds']:5.1f}s "
            f"${row['usd_upper_bound']:.4f} revised={row['revised']} open={len(row['open_problems'])}",
            flush=True,
        )
log["total"] = {
    k: round(sum(r[k] for r in log["reports"]), 4)
    for k in ("claims", "seconds", "prompt_tokens", "completion_tokens", "usd_upper_bound")
}
(OUT / "run.json").write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
print("TOTAL", log["total"])
