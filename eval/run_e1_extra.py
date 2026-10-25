"""Agent, linear and Afzal et al. on the ten E1-only papers, with the same steps and settings as for the human-study papers."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

REPO = Path.cwd()
OUT = REPO / "eval" / "out" / "e1_extra"
sys.path.insert(0, str(REPO / "src" / "novelty_assessment"))
ENV = {**os.environ, "PYTHONUTF8": "1"}
MODEL_CA = "gpt-5.6-luna"

keys = list(yaml.safe_load((REPO / "final_evaluation/config/e1_extra.yaml").read_text(encoding="utf-8"))["papers"])
if len(sys.argv) > 1:
    keys = [k for k in keys if k in sys.argv[1].split(",")]


def run(cmd, log):
    t = time.time()
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(f"\n$ {' '.join(cmd)}\n"); fh.flush()
        rc = subprocess.run(cmd, cwd=REPO, env=ENV, stdout=fh, stderr=subprocess.STDOUT).returncode
    return rc, round(time.time() - t)


def artifacts_done(k):
    for v in ("agent", "linear"):
        p = REPO / "data" / k / f"{k}_artifact_a_{v}.json"
        b = REPO / "data" / k / f"{k}_artifact_b_{v}.json"
        if not (p.is_file() and b.is_file()):
            return False
        if not (json.loads(b.read_text(encoding="utf-8")).get("paper_summary") or {}).get("main_novelty_concern"):
            return False
    return True


def assessed(k):
    for v in ("agent", "linear"):
        b = json.loads((REPO / "data" / k / f"{k}_artifact_b_{v}.json").read_text(encoding="utf-8"))
        if not all(x.get("claim_assessment") for x in b.get("per_claim") or []):
            return False
    return True


def afzal_done(k):
    d = REPO / "data" / k
    return (d / "summary.txt").is_file() and (d / "novelty_delta_analysis.txt").is_file()


failed = []
for k in keys:
    print(f"\n===== {k} =====", flush=True)
    meta_p = OUT / f"{k}__run_meta.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.is_file() else {"submission": k}
    try:
        if artifacts_done(k):
            print("  agent/linear: already done", flush=True)
        else:
            rc, s = run([sys.executable, "eval/run_pilot.py", "--submission", k, "--variant", "both"],
                        OUT / f"{k}__pilot.log")
            meta["pilot"] = {"rc": rc, "seconds": s, "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            print(f"  agent/linear: rc={rc} {s}s", flush=True)
            if rc != 0 or not artifacts_done(k):
                raise RuntimeError(f"run_pilot rc={rc}")

        if assessed(k):
            print("  claim assessments: already done", flush=True)
        else:
            import claim_assessment as ca
            from agent.claim_agent import _usd
            rows = []
            for v in ("agent", "linear"):
                src = REPO / "data" / k / f"{k}_artifact_b_{v}.json"
                bak = OUT / "artifact_b_before_claim_assessment" / src.name
                bak.parent.mkdir(parents=True, exist_ok=True)
                if not bak.exists():
                    shutil.copy2(src, bak)
                t = time.time()
                res = ca.build("data", k, v, model_name=MODEL_CA)
                pt = sum(r["usage"]["prompt_tokens"] or 0 for r in res)
                ct = sum(r["usage"]["completion_tokens"] or 0 for r in res)
                rows.append({"variant": v, "claims": len(res), "seconds": round(time.time() - t, 1),
                             "prompt_tokens": pt, "completion_tokens": ct,
                             "usd_upper_bound": round(_usd(MODEL_CA, pt, ct), 4),
                             "prompt_version": ca.PROMPT_VERSION, "prompt_sha256": ca.prompt_sha256()})
            meta["claim_assessment"] = rows
            print(f"  claim assessments: {[(r['variant'], r['claims'], r['usd_upper_bound']) for r in rows]}", flush=True)

        if afzal_done(k):
            print("  afzal: already done", flush=True)
        else:
            rc1, s1 = run([sys.executable, "eval/afzal_adapter.py", "--data-dir", "data", "--submission-id", k],
                          OUT / f"{k}__afzal_adapter.log")
            rc2, s2 = run([sys.executable, "src/novelty_assessment/pipeline.py", "--data-dir", "data",
                           "--submission-id", k, "--model", "gpt-4.1"], OUT / f"{k}__afzal_pipeline.log")
            meta["afzal"] = {"rc": [rc1, rc2], "seconds": s1 + s2,
                             "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            print(f"  afzal: rc={rc1}/{rc2} {s1 + s2}s", flush=True)
            if rc1 or rc2 or not afzal_done(k):
                raise RuntimeError(f"afzal rc={rc1}/{rc2}")
    except Exception as e:
        failed.append(k)
        meta["error"] = repr(e)[:300]
        print(f"  FAILED: {e!r}"[:300], flush=True)
    meta_p.write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")

print("\nFAILED: " + (", ".join(failed) if failed else "none"), flush=True)
