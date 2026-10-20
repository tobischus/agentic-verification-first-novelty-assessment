import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import SplitView from "../pdf/SplitView.jsx";
import PdfViewer, { colorFor } from "../pdf/PdfViewer.jsx";
import { DEGREE_LABEL } from "../verdict";
import { claimOfPassages } from "./assessmentStyle.js";
import {
  DIM,
  claimColor,
  claimSection,
  detailRefs,
  quotedTexts,
  renderExport,
} from "./exportRender.jsx";

// The Review tab walks the claims one at a time. For a finished claim it shows that
// claim's section of `/review/export` -- the same text, parsed by the same renderer as the
// Summary tab (./exportRender.jsx), in the same styles -- so the two tabs cannot disagree
// about a claim. What only this tab adds is the live agent view while a claim is computed,
// which is not part of the report.

// DOM ids of this tab's copy of the report; the Summary tab renders its copy as "se".
const ID_PREFIX = "rv";
const EMPTY_INDEX = { submission: [], papers: {}, refs: {}, claim_anchors: {} };

const traceImportant = (s = "") =>
  s.includes("mandatory initial read") ||
  s.includes("read_more") ||
  s.includes("dismissal_falsification") ||
  s.includes("dismissed after") ||
  s.includes("SEMANTIC DEGREE:") ||
  s.includes("GROUNDED OWNED PAIRS:") ||
  s.includes("EVIDENCE CHECK:") ||
  s.includes("MATERIAL AGREEMENT:") ||
  s.includes("evidence gate REFUSED") ||
  s.includes("evidence gate passed") ||
  s.includes("INSUFFICIENT");

const prettyTrace = (s = "") =>
  s
    .replace(/^\[read \d+\]\s*/, "")
    .replace(/^\[\d+\]\s*/, "")
    .replace("SEMANTIC DEGREE:", "Semantic comparison:")
    .replace("GROUNDED OWNED PAIRS:", "Grounded + owned pairs:")
    .replace("EVIDENCE CHECK: status=", "Evidence check:")
    .replace("compared, evidence gate passed", "✓ Evidence gate passed")
    .replace(
      "evidence gate REFUSED -> read again:",
      "↻ Evidence gate refused → read again:",
    );

export default function ReviewWalkthrough({ submissionId, active, autoStart, onFinish }) {
  const [list, setList] = useState(null);
  const [err, setErr] = useState("");
  const [started, setStarted] = useState(false);
  const [ci, setCi] = useState(0);
  const [cache, setCache] = useState({}); // claim_id -> computed claim data (process view)
  const [loading, setLoading] = useState(false);
  const [live, setLive] = useState(null); // live agent progress for the current claim
  // The report as the export prints it ({text, index}); a finished claim is read from it.
  const [report, setReport] = useState(null);
  const [assessing, setAssessing] = useState(false);
  const [finishing, setFinishing] = useState(false);
  // Which document the right-hand pane shows and which passage it should scroll to.
  // paperId === null means the submission itself, where the reader starts.
  const [reader, setReader] = useState({ paperId: null, focusId: null });
  const pollRef = useRef(null);
  const trajRef = useRef(null);
  // The review starts on its own when the reviewer approved the related work in this
  // session, or when claim 1 is already computed (showing it costs nothing). A reload of
  // an unreviewed submission never starts the agent -- that would spend without a click.
  const startRef = useRef(null);
  const autoStarted = useRef(false);
  useEffect(() => {
    if (!list || started || autoStarted.current || !active || !startRef.current) return;
    if (autoStart || list.claims[0]?.computed) {
      autoStarted.current = true;
      startRef.current();
    }
  }, [list, started, active, autoStart]);

  useEffect(() => {
    api
      .reviewClaims(submissionId)
      .then(setList)
      .catch((e) => setErr(String(e)));
    return () => clearTimeout(pollRef.current);
  }, [submissionId]);

  useEffect(() => {
    setReader({ paperId: null, focusId: null });
  }, [ci]);

  const trajLen = live?.trajectory?.length || 0;
  const paperTraceLen = (live?.paper_traces || []).reduce(
    (n, p) => n + (p.trace || []).length,
    0,
  );

  useEffect(() => {
    if (trajRef.current) {
      trajRef.current.scrollTop = trajRef.current.scrollHeight;
    }
  }, [trajLen, paperTraceLen]);

  if (err) return <div className="error">{err}</div>;
  if (!list) return <div className="panel">Loading review…</div>;

  const claims = list.claims;
  const n = claims.length;

  const pollLive = (id) =>
    new Promise((resolve, reject) => {
      let fails = 0;
      const tick = async () => {
        let d = null;
        try {
          d = await api.claimLive(submissionId, id);
          fails = 0;
        } catch (e) {
          // transient network/timeout hiccup: keep polling, give up after 5 in a row
          if (++fails >= 5) {
            reject(e);
            return;
          }
        }
        if (d) {
          setLive(d);
          // only stop on a done payload that carries the assembled review
          if (d.status === "done" && d.review) {
            resolve(d);
            return;
          }
          if (d.status === "error") {
            reject(new Error(d.error || "agent error"));
            return;
          }
        }
        pollRef.current = setTimeout(tick, 1200);
      };
      pollRef.current = setTimeout(tick, 400);
    });

  // A finished claim is shown from the report itself: make sure its claim-level
  // assessment is written (a no-op when it is current), then re-read the export.
  const refreshReport = async (cid) => {
    setAssessing(true);
    try {
      try {
        await api.ensureClaimAssessment(submissionId, cid);
      } catch {
        // not fatal: the export then prints the recorded rationale instead
      }
      const [text, index] = await Promise.all([
        api.reviewExport(submissionId),
        api.quoteIndex(submissionId),
      ]);
      setReport({ text, index });
    } catch (e) {
      setErr(String(e));
    } finally {
      setAssessing(false);
    }
  };

  const loadClaim = async (idx) => {
    setCi(idx);
    setStarted(true);
    window.scrollTo(0, 0);
    const id = claims[idx].claim_id;
    if (cache[id]) {
      setLive(null);
      await refreshReport(id);
      return;
    }
    setLoading(true);
    setLive({ status: "running", step: 0, trajectory: [], cost: { usd: 0 } });
    let ok = false;
    try {
      const resp = await api.computeClaim(submissionId, id);
      const d = resp.status === "done" ? resp : await pollLive(id);
      if (d.review) setCache((c) => ({ ...c, [id]: d.review }));
      ok = true;
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
    if (ok) await refreshReport(id);
  };

  // After the last claim: every claim assessment current + the paper-level novelty
  // summary, then hand over to the Summary tab.
  const finish = async () => {
    setFinishing(true);
    try {
      await api.finalizeReview(submissionId);
    } catch (e) {
      setFinishing(false);
      setErr(String(e));
      return;
    }
    setFinishing(false);
    if (onFinish) onFinish();
  };

  const claim = started ? claims[ci] : null;
  const data = claim ? cache[claim.claim_id] : null;

  // advance to the next claim, or finish after the last one
  const goNext = async () => {
    if (ci < n - 1) await loadClaim(ci + 1);
    else await finish();
  };
  // go back to a previous (already reviewed) claim -- instant, it's cached
  const goPrev = async () => {
    if (ci > 0) await loadClaim(ci - 1);
  };

  startRef.current = () => loadClaim(0);

  // ---------- before the first claim ----------
  if (!started) {
    const pending = autoStart || claims[0]?.computed;
    return (
      <div className="panel review-start">
        <div className="eyebrow">Review</div>
        <h2>
          {n} claims · {list.n_reference_papers} reference papers
        </h2>
        {pending ? (
          <div className="live-head">
            <div className="spinner" />
            <div className="muted">Starting the review of claim 1…</div>
          </div>
        ) : (
          <>
            <p className="muted lede">
              For each claim, an agent reads the candidate papers and compares them with the
              claim. An overlap counts only with quotes verified verbatim in both papers.
            </p>
            <button disabled={loading} onClick={() => loadClaim(0)}>
              {loading ? "Starting…" : "Start the review"}
            </button>
          </>
        )}
      </div>
    );
  }

  // ---------- live progress (agent running) ----------
  const livePanel = () => {
    const lv = live || {};
    const traj = lv.trajectory || [];
    const step = lv.step || 0;
    const maxs = lv.max_steps || 0;
    const paperTraces = lv.paper_traces || [];
    return (
      <div className="rv-block">
        <div className="live-head">
          <div className="spinner" />
          <div className="live-title">
            <strong>Reviewing claim {ci + 1}…</strong>
            <div className="muted">{lv.last_action || "starting up"}</div>
          </div>
          <div className="live-metrics">
            <span className="lm">
              Step {step}
              {maxs ? `/${maxs}` : ""}
            </span>
            <span className="lm">{lv.examined ?? 0} examined</span>
            <span className="lm">{lv.comparisons ?? 0} compared</span>
            {(lv.retrieval_rounds ?? 0) > 0 && (
              <span className="lm">{lv.retrieval_rounds} new searches</span>
            )}
          </div>
        </div>
        {maxs > 0 && (
          <div className="live-bar">
            <div
              className="live-fill"
              style={{
                width: `${Math.min(100, Math.round((step / maxs) * 100))}%`,
              }}
            />
          </div>
        )}
        <div className="paper-traces" ref={trajRef}>
          {paperTraces.length === 0 && (
            <div className="muted">Reading prior work…</div>
          )}

          {paperTraces.map((p) => (
            <div
              className={
                "paper-trace-card" + (p.insufficient ? " insufficient" : "")
              }
              key={p.paper_id}
            >
              <div className="pt-head">
                <strong>{p.title || p.paper_id}</strong>

                {p.overlap_degree && (
                  <span className="relbadge mid">
                    {DEGREE_LABEL[p.overlap_degree] || p.overlap_degree}
                  </span>
                )}
              </div>

              <div className="pt-summary">
                <span>{p.grounded_pairs} grounded + owned pair(s)</span>
                {p.evidence_status && (
                  <span>evidence: {p.evidence_status}</span>
                )}
                {p.insufficient && <span>⚠ insufficient</span>}
              </div>

              <div className="pt-lines">
                {(p.trace || []).filter(traceImportant).map((line, i) => (
                  <div className="pt-line" key={i}>
                    {prettyTrace(line)}
                  </div>
                ))}
              </div>

              <details className="raw-trace">
                <summary>Full audit trace</summary>
                {(p.trace || []).map((line, i) => (
                  <div key={i}>{line}</div>
                ))}
              </details>
            </div>
          ))}

          <details className="raw-trace global">
            <summary>Raw execution log</summary>
            {traj.map((t) => (
              <div key={t.step}>
                {t.action}: {t.detail}
              </div>
            ))}
          </details>
        </div>
      </div>
    );
  };

  // ---------- one finished claim: its section of the report ----------
  const claimNo = ci + 1; // the export numbers the non-rejected claims in this order
  const text = report?.text || "";
  const index = report?.index || EMPTY_INDEX;
  const section = claimSection(text, claimNo);
  const ready = !!data && !loading && !assessing && !!section;

  // Colours exactly as in the Summary tab: a passage takes its claim's colour, a prior
  // paper its own, both assigned over the whole report.
  const claimOf = claimOfPassages(text, index);
  const shown = quotedTexts(section);
  const anchor = index.claim_anchors?.[String(claimNo)];
  const refToPaper = {};
  Object.entries(index.refs || {}).forEach(([pid, ref]) => {
    refToPaper[ref] = pid;
  });
  const claimPapers = detailRefs(section)
    .map((r) => refToPaper[r])
    .filter((pid) => pid && index.papers?.[pid]);
  const paperColor = {};
  Object.keys(index.papers || {}).forEach((pid, i) => {
    paperColor[pid] = colorFor(i + 1);
  });
  const shade = (id, color) =>
    reader.focusId && id !== reader.focusId ? color + DIM : color;
  const readerPaper = reader.paperId ? index.papers?.[reader.paperId] : null;
  // Only the passages this claim's section prints, so the PDF marks what the left shows.
  const highlights = readerPaper
    ? readerPaper.quotes
        .filter((q) => shown.has(q.text))
        .map((q) => ({
          id: q.id,
          text: q.text,
          color: shade(q.id, paperColor[reader.paperId]),
        }))
    : (index.submission || [])
        .filter((q) => shown.has(q.text) || q.id === anchor?.id)
        .map((q) => ({
          id: q.id,
          text: q.text,
          color: shade(
            q.id,
            claimOf.has(q.id) ? claimColor(claimOf.get(q.id)) : colorFor(0),
          ),
        }));
  const onPick = (target) =>
    setReader({ paperId: target.paperId, focusId: target.id });
  const readerUrl = reader.paperId
    ? api.paperPdfUrl(submissionId, reader.paperId)
    : api.pdfUrl(submissionId);

  const viewer = (
    <div className="pdfpane">
      <div className="pdfpicker">
        <select
          value={reader.paperId || ""}
          onChange={(e) =>
            setReader({ paperId: e.target.value || null, focusId: null })
          }
        >
          <option value="">The submission</option>
          {claimPapers.map((pid) => (
            <option key={pid} value={pid}>
              {index.papers[pid].title}
            </option>
          ))}
        </select>
      </div>
      <PdfViewer
        key={readerUrl}
        url={readerUrl}
        highlights={highlights}
        focusId={reader.focusId}
      />
    </div>
  );

  const pending = () => {
    if (loading) return livePanel();
    if (assessing || !data)
      return (
        <div className="rv-block">
          <div className="live-head">
            <div className="spinner" />
            <div className="live-title">
              <strong>Preparing the report for claim {claimNo}…</strong>
              <div className="muted">
                the claim-level assessment, as the final report prints it
              </div>
            </div>
          </div>
        </div>
      );
    return (
      <div className="error">
        Claim {claimNo} is missing from the report. Reload the tab or run the review
        for this claim again.
      </div>
    );
  };

  const panel = (
    <div className="panel review-wt">
      <div className="review-head">
        <div>
          <div className="eyebrow">Review</div>
          <h2>
            Claim {ci + 1} of {n}
          </h2>
          <div className="muted">{list.n_reference_papers} reference papers</div>
        </div>
        <div className="review-head-right">
          <div className="claim-dots">
            {claims.map((_, i) => (
              <span
                key={i}
                className={
                  "cdot" + (i < ci ? " done" : i === ci ? " current" : "")
                }
              />
            ))}
          </div>
        </div>
      </div>

      {ready ? (
        <>
          <div className="se-export rv-report">
            {renderExport(section, index, reader.focusId, onPick, claimOf, {
              idPrefix: ID_PREFIX,
              grouped: true,
              openClaims: false,
            })}
          </div>
          <div className="review-actions split">
            <button
              className="secondary"
              disabled={finishing || ci === 0}
              onClick={goPrev}
            >
              Previous claim
            </button>
            <button disabled={finishing} onClick={goNext}>
              {ci < n - 1
                ? "Confirm and next claim"
                : finishing
                  ? "Writing the novelty summary…"
                  : "Confirm and finish"}
            </button>
          </div>
          {finishing && (
            <p className="muted rv-finishing">
              Bringing every claim-level assessment up to date and writing the
              paper-level novelty summary…
            </p>
          )}
        </>
      ) : (
        <>
          <div className="claim-under-review">
            <div className="cur-label">Claim under review</div>
            <div className="cur-text">{claim.claim_text}</div>
          </div>
          {pending()}
        </>
      )}
    </div>
  );

  return <SplitView storageKey="review" left={panel} right={viewer} />;
}
