import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import PipelineCostBadge from "./PipelineCostBadge.jsx";
import SplitView from "../pdf/SplitView.jsx";
import PdfViewer, { colorFor } from "../pdf/PdfViewer.jsx";
import { DEGREE_LABEL } from "../verdict";

// icon per agent tool action, for the live trajectory
const ACTION_ICON = {
  list_related_work: "📚",
  search_submission: "🔎",
  list_sections: "🗂️",
  read_paper: "📄",
  retrieve_more: "🌐",
  record_comparison: "🔀",
  finish: "🏁",
  triage: "⚡",
  triage_result: "⚡",
  deep_dive: "🔬",
  understand_submission: "📝",
  read_sections: "🗂️",
};
const usd = (v) => "$" + Number(v || 0).toFixed(4);

// "Haoyu Han, Harry Shomer, ..." (+ year) -> "Han et al. · 2025"
function fmtAuthors(a, year) {
  const names = (a || "")
    .split(/,\s*/)
    .map((s) => s.trim())
    .filter(Boolean);
  let cite = "";
  if (names.length) {
    const first = names[0].split(/\s+/).slice(-1)[0];
    cite = names.length > 1 ? `${first} et al.` : names[0];
  }
  return [cite, year].filter(Boolean).join(" · ");
}

// A flowing explanation built from prose + verbatim quote segments. Quote segments
// (verified === true) render as a quote with a ✓ meaning "appears verbatim in the source".
function Realization({ segments, docKey, onPick, activeId }) {
  const segs = (segments || []).filter((s) => (s.content || "").trim());
  if (!segs.length) return null;
  const hasQuote = segs.some((s) => s.kind === "quote");
  // Quote ids must be stable across renders AND across the two places the same list is
  // used (here and when the highlight set is built), so they are derived from the
  // document key and the segment's position -- never from array identity.
  const qid = (i) => `${docKey}#${i}`;
  return (
    <div className="realization">
      {segs.map((s, i) =>
        s.kind === "quote" ? (
          <blockquote
            className={
              "rz-quote" +
              (onPick ? " qjump" : "") +
              (activeId === qid(i) ? " active" : "")
            }
            key={i}
            onClick={onPick ? () => onPick(qid(i)) : undefined}
            title={onPick ? "Show this passage in the PDF" : undefined}
          >
            <span
              className="rz-qmark"
              title="This quote appears verbatim in the source text"
            >
              ✓
            </span>
            <span className="rz-qtext">{s.content}</span>
          </blockquote>
        ) : "verified" in s ? (
          // stored as {kind:'text', verified:false}: copied from the source, but the
          // checker could not confirm it there
          <div className="rz-unverified" key={i}>
            <span className="rz-ulab">
              Quoted from the source but not confirmed verbatim
            </span>
            {s.content}
          </div>
        ) : (
          <p className="rz-text" key={i}>
            {s.content}
          </p>
        ),
      )}
      {hasQuote && (
        <div className="rz-legend">
          <span className="ok">✓</span> = quote appears verbatim in the paper
          {onPick && " · click a quote to jump to it in the PDF"}
        </div>
      )}
    </div>
  );
}

/** A pair's quotes as highlights, for whichever side's document is on the right.
 *
 *  Ids must equal what EvidencePairs' click targets build (`${docKey}#pair${pair_index}`),
 *  because the two are matched by exact string equality in PdfViewer -- this used to key
 *  off the pair's position in the array (`#p${i}`) instead of its stable `pair_index`, so
 *  the two ends never agreed once anything (grouping, a dropped unverified pair) made a
 *  pair's array position differ from its backend index. That silently broke every jump.
 */
function pairQuotesOf(pairs, docKey, side, color) {
  return (pairs || [])
    .map((q, i) => ({ q, id: `${docKey}#pair${q.pair_index ?? i}` }))
    .filter(({ q }) => q.claim_quote && q.paper_quote)
    .map(({ q, id }) => ({
      id,
      text: side === "paper" ? q.paper_quote : q.claim_quote,
      color,
    }));
}

/** A claim-evidence pair: one sentence of the submission beside the prior paper's own
 *  sentence saying the same thing. Both sides were verified against their own document,
 *  and both are clickable -- the point of a pair is that the reviewer can check each half
 *  where it actually stands, so each side opens ITS document, not a shared one. */
function EvidencePairs({
  pairs,
  paperId,
  docKey,
  activeId,
  onPickSubmission,
  onPickPaper,
  evidenceStatus,
  supportingPairIndices,
  evidenceReasoning,
}) {
  const ok = (pairs || []).filter((q) => q.claim_quote && q.paper_quote);

  if (!ok.length) return null;

  const supporting = new Set(supportingPairIndices || []);

  // For a material finding, distinguish pairs that actually support
  // material overlap from other grounded candidate correspondences.
  const main =
    evidenceStatus === "material" && supporting.size > 0
      ? ok.filter((q) => supporting.has(q.pair_index))
      : ok;

  const additional =
    evidenceStatus === "material" && supporting.size > 0
      ? ok.filter((q) => !supporting.has(q.pair_index))
      : [];

  // Group identical submission spans so the same verified quote
  // is shown only once.
  const groupBySubmissionQuote = (items) => {
    const groups = new Map();

    items.forEach((q) => {
      const key = (q.claim_quote || "").replace(/\s+/g, " ").trim();

      if (!groups.has(key)) {
        groups.set(key, []);
      }

      groups.get(key).push(q);
    });

    return [...groups.entries()];
  };

  const renderGroups = (items, prefix) =>
    groupBySubmissionQuote(items).map(([claimQuote, group], gi) => {
      // Must equal the id pairQuotesOf built for this same pair (`${docKey}#pair${pair_index}`,
      // via `subpair:${paperId}` as that docKey) -- a group-position id (`#${prefix}${gi}`)
      // never matched anything in the highlights array and silently broke the jump.
      // The group's first pair stands for the whole group: they share this submission span.
      const subId = `subpair:${paperId}#pair${group[0].pair_index}`;

      return (
        <div className="ev-pair-group" key={`${prefix}-${gi}`}>
          <div className="ev-pair-group-label">
            Submission contribution span
          </div>

          <blockquote
            className={
              "rz-quote qjump pair-sub" + (activeId === subId ? " active" : "")
            }
            onClick={() => onPickSubmission(subId)}
            title="Show this passage in your paper"
          >
            <span
              className="rz-qmark"
              title="Verified verbatim in the submission"
            >
              ✓
            </span>
            <span className="ev-pairside">Your paper</span>
            <span className="rz-qtext">{claimQuote}</span>
          </blockquote>

          <div className="ev-correspondences">
            {group.map((q) => {
              const pid = `${docKey}#pair${q.pair_index}`;

              return (
                <div className="ev-correspondence" key={q.pair_index}>
                  {q.rationale && (
                    <div className="ev-pairwhy">{q.rationale}</div>
                  )}

                  <blockquote
                    className={
                      "rz-quote qjump pair-pap" +
                      (activeId === pid ? " active" : "")
                    }
                    onClick={() => onPickPaper(pid)}
                    title="Show this passage in the prior paper"
                  >
                    <span
                      className="rz-qmark"
                      title="Verified verbatim in the prior paper"
                    >
                      ✓
                    </span>
                    <span className="ev-pairside">This paper</span>
                    <span className="rz-qtext">{q.paper_quote}</span>
                  </blockquote>
                </div>
              );
            })}
          </div>
        </div>
      );
    });

  return (
    <div className="ev-pairs">
      <div className="ev-sublab">
        Grounded evidence for the assessed overlap
        <span className="ev-pairhint">
          {" "}
          ·{" "}
          {evidenceStatus === "material"
            ? `${main.length} supporting grounded ${
                main.length === 1 ? "pair" : "pairs"
              }`
            : `${ok.length} grounded ${ok.length === 1 ? "pair" : "pairs"}`}
        </span>
      </div>

      {evidenceStatus && (
        <div className="ev-evidence-status">
          Evidence check: <strong>{evidenceStatus}</strong>
          {evidenceStatus === "material" &&
            ` · ${main.length} of ${ok.length} grounded candidates support the overlap`}
        </div>
      )}

      {evidenceReasoning && (
        <div className="ev-evidence-reason">{evidenceReasoning}</div>
      )}

      {renderGroups(main, "main")}

      {additional.length > 0 && (
        <details className="ev-additional-pairs" open>
          <summary>
            {additional.length} additional grounded candidate
            {additional.length === 1 ? "" : "s"} not used as material support
          </summary>

          {renderGroups(additional, "additional")}
        </details>
      )}
    </div>
  );
}

/** What the submission still holds against this paper, and what the check took back.
 *
 *  A delta is a claim of ABSENCE, and absence cannot be quoted. So both halves that can be
 *  are shown: the submission's own sentence stating the thing, and the nearest passage the
 *  prior paper actually has -- the one a reviewer would be shown if they asked "are you
 *  sure it does not do that?". Both are verified verbatim against their own document.
 *
 *  A delta the nearest passage refuted is shown too, as withdrawn. A paper that turns out
 *  to deliver what the submission thought was its own is the most useful thing this
 *  comparison can find, and hiding it would leave the panel tidier than the evidence.
 */
function DeltaEvidence({ held, withdrawn }) {
  const h = held || [];
  const w = withdrawn || [];
  if (!h.length && !w.length) return null;
  return (
    <div className="ev-delta">
      <div className="ev-sublab">What the submission still has</div>
      {h.map((d, i) => (
        <div className="ev-deltaitem" key={"h" + i}>
          <div className="ev-deltawhat">{d.what}</div>
          {d.note && <div className="ev-pairwhy">{d.note}</div>}
          {d.claim_quote && (
            <blockquote className="rz-quote pair-sub">
              <span
                className="rz-qmark"
                title="Verified verbatim in the submission"
              >
                ✓
              </span>
              <span className="ev-pairside">Your paper</span>
              <span className="rz-qtext">{d.claim_quote}</span>
            </blockquote>
          )}
          {d.paper_nearest_verified && d.paper_nearest_quote ? (
            <div className="ev-closest">
              <span className="ev-closestlab">
                The nearest this paper comes
              </span>
              <span className="ev-closesttext">{d.paper_nearest_quote}</span>
            </div>
          ) : d.nothing_of_the_kind ? (
            <div className="ev-closest">
              <span className="ev-closestlab">
                The paper holds nothing of the kind to point at.
              </span>
            </div>
          ) : null}
        </div>
      ))}
      {w.map((d, i) => (
        <div className="ev-deltaitem withdrawn" key={"w" + i}>
          <div className="ev-deltawhat">
            <span className="ev-withdrawtag">withdrawn</span> {d.what}
          </div>
          {d.note && <div className="ev-pairwhy">{d.note}</div>}
          {d.paper_nearest_quote && d.paper_nearest_verified && (
            <blockquote className="rz-quote pair-pap">
              <span
                className="rz-qmark"
                title="Verified verbatim in the prior paper"
              >
                ✓
              </span>
              <span className="ev-pairside">This paper</span>
              <span className="rz-qtext">{d.paper_nearest_quote}</span>
            </blockquote>
          )}
        </div>
      ))}
    </div>
  );
}

/** How far this comparison got, and what it could not settle.
 *
 *  `confidence` and the open points come from a gate in code, not from the model: a
 *  comparison whose questions were answered reads differently from one that ran out of
 *  rounds, and until now the artifact could not tell them apart.
 */
function Deepening({ d }) {
  if (!d || !d.rounds) return null;
  const open = d.open || [];
  return (
    <div className={"ev-deepen conf-" + (d.confidence || "low")}>
      <span className="ev-deepenlab">
        {d.rounds} deepening round{d.rounds === 1 ? "" : "s"} · {d.confidence}{" "}
        confidence
      </span>
      {open.length > 0 && (
        <ul className="ev-openlist">
          {open.map((o, i) => (
            <li key={i}>{o}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** The verified quote segments of a realization, as highlights for the viewer. */
function quotesOf(segments, docKey, color) {
  return (segments || [])
    .filter((s) => (s.content || "").trim())
    .map((s, i) => ({ seg: s, id: `${docKey}#${i}` }))
    .filter(({ seg }) => seg.kind === "quote")
    .map(({ seg, id }) => ({ id, text: seg.content, color }));
}

// Outcome of the on-demand GROBID full-text fetch for a deep-dived paper. Only
// rendered when a fetch was actually attempted (null = abstract-only triage, no
// deep dive) -- "already_had" is silent (nothing noteworthy happened).
const FT_FETCH_LABEL = {
  ok: { text: "Full text parsed for this deep dive", cls: "ok" },
  no_pdf: {
    text: "No PDF available — compared using the abstract only",
    cls: "warn",
  },
  parse_empty: {
    text: "PDF has no extractable text (scanned) — compared using the abstract only",
    cls: "warn",
  },
  parse_error: {
    text: "PDF could not be parsed — compared using the abstract only",
    cls: "warn",
  },
  // legacy statuses from runs before the in-process parser replaced GROBID
  grobid_unreachable: {
    text: "Full-text parsing service was down — compared using the abstract only",
    cls: "warn",
  },
  grobid_empty: {
    text: "PDF could not be parsed (scanned/empty) — compared using the abstract only",
    cls: "warn",
  },
  grobid_error: {
    text: "Full-text parsing failed — compared using the abstract only",
    cls: "warn",
  },
};
function FulltextFetchBadge({ status }) {
  const info = FT_FETCH_LABEL[status];
  if (!info) return null;
  return (
    <div className={"ft-fetch-badge " + info.cls}>
      {info.cls === "ok" ? "📄" : "⚠"} {info.text}
    </div>
  );
}

// Human-readable duration: 2m 05s / 47.3s / 0.8s
const dur = (s) => {
  const v = Number(s || 0);
  if (v >= 60) {
    const m = Math.floor(v / 60);
    return `${m}m ${String(Math.round(v - m * 60)).padStart(2, "0")}s`;
  }
  return `${v.toFixed(1)}s`;
};
const PHASE_LABEL = {
  rerank: "Rerank pool (relevance)",
  understand_submission: "Read the submission for this claim",
  triage: "Triage whole pool (abstracts)",
  deep_dive_total: "Deep dives (section-based compare)",
  reentry: "Re-entry retrieval + triage",
  other: "Indexing / bookkeeping",
};
const PHASE_ORDER = [
  "rerank",
  "understand_submission",
  "triage",
  "deep_dive_total",
  "reentry",
  "other",
];

// Wall-clock breakdown for one claim: where the time went. Almost all of it is LLM
// latency (triage + the per-paper deep-dive comparisons); PDF parsing is ~1s each.
function TimingPanel({ timings }) {
  const [open, setOpen] = useState(false);
  if (!timings || !timings.total) return null;
  const total = Number(timings.total);
  const rows = PHASE_ORDER.filter((k) => Number(timings[k]) > 0)
    .map((k) => ({ k, label: PHASE_LABEL[k], s: Number(timings[k]) }))
    .sort((a, b) => b.s - a.s);
  const papers = timings.deep_dive_papers || [];
  const slowest = rows[0];
  return (
    <div className="rv-block timing-block">
      <div
        className="rv-h sm timing-head"
        onClick={() => setOpen((o) => !o)}
        style={{ cursor: "pointer" }}
      >
        <span className="rv-ic">⏱️</span>
        <h4>This claim took {dur(total)}</h4>
        <span className="timing-toggle">
          {open ? "hide breakdown ▲" : "show breakdown ▼"}
        </span>
      </div>
      {slowest && (
        <p className="muted rv-sub">
          Biggest chunk: <strong>{slowest.label}</strong> ({dur(slowest.s)},{" "}
          {Math.round((100 * slowest.s) / total)}%). This is model latency —
          deep-dive comparisons and pool triage dominate; PDF parsing is ~1s per
          paper.
        </p>
      )}
      {open && (
        <>
          <div className="timing-bars">
            {rows.map((r) => (
              <div className="timing-row" key={r.k}>
                <div className="tr-label">{r.label}</div>
                <div className="tr-bar-wrap">
                  <div
                    className="tr-bar"
                    style={{ width: `${Math.max(2, (100 * r.s) / total)}%` }}
                  />
                </div>
                <div className="tr-val">
                  {dur(r.s)} · {Math.round((100 * r.s) / total)}%
                </div>
              </div>
            ))}
          </div>
          {papers.length > 0 && (
            <div className="timing-papers">
              <div className="tp-title">
                Per deep-dive paper (parse vs. LLM compare)
              </div>
              {papers.map((p, i) => (
                <div className="tp-row" key={i}>
                  <div className="tp-name" title={p.title}>
                    {p.title || p.paper_id}
                  </div>
                  <div className="tp-nums">
                    <span className="tp-parse" title="PDF parsing (in-process)">
                      parse {dur(p.parse_s)}
                    </span>
                    <span className="tp-cmp" title="LLM comparison">
                      compare {dur(p.compare_s)}
                    </span>
                    <span className="tp-tot">= {dur(p.total_s)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function ReviewWalkthrough({ submissionId, onFinish }) {
  const [list, setList] = useState(null);
  const [err, setErr] = useState("");
  const [started, setStarted] = useState(false);
  const [ci, setCi] = useState(0);
  const [cache, setCache] = useState({}); // claim_id -> computed claim data
  const [loading, setLoading] = useState(false);
  const [live, setLive] = useState(null); // live agent progress for the current claim
  const [costTick, setCostTick] = useState(0); // bump to re-fetch the pipeline cost badge
  // Which document the right-hand pane shows and which quote it should scroll to.
  // paperId === null means the submission itself, which is where the reader starts:
  // the reviewer's own paper, with every passage the assessment quotes marked in it.
  const [reader, setReader] = useState({ paperId: null, focusId: null });
  const pollRef = useRef(null);
  const trajRef = useRef(null);

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

  const loadClaim = async (idx) => {
    setCi(idx);
    setStarted(true);
    window.scrollTo(0, 0);
    const id = claims[idx].claim_id;
    if (cache[id]) {
      setLive(null);
      return;
    }
    setLoading(true);
    setLive({ status: "running", step: 0, trajectory: [], cost: { usd: 0 } });
    try {
      const resp = await api.computeClaim(submissionId, id);
      const d = resp.status === "done" ? resp : await pollLive(id);
      if (d.review) setCache((c) => ({ ...c, [id]: d.review }));
      setCostTick((t) => t + 1);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  const claim = started ? claims[ci] : null;
  const data = claim ? cache[claim.claim_id] : null;
  const ready = data && !loading;

  // advance to the next claim, or hand off to the Summary tab after the last one
  const goNext = async () => {
    if (ci < n - 1) await loadClaim(ci + 1);
    else if (onFinish) onFinish();
  };
  // go back to a previous (already reviewed) claim -- instant, it's cached
  const goPrev = async () => {
    if (ci > 0) await loadClaim(ci - 1);
  };

  // ---------- intro ----------
  if (!started) {
    return (
      <div className="panel review-intro">
        <div className="bot">🤖</div>
        <h2>Evidence-Based Novelty Review</h2>
        <p className="muted">
          {n} claims ready · {list.n_reference_papers} reference papers
          selected.
        </p>
        <p className="muted">
          For each claim, an agent reads the submission's own sections about the
          contribution, then reads the relevant prior work section by section
          and gathers <strong>verifiable evidence</strong> of any overlap.
          Claims are analysed one at a time.
        </p>
        <button
          className="begin"
          disabled={loading}
          onClick={() => loadClaim(0)}
        >
          {loading ? "Analysing claim 1…" : "✨ Start Claim-Level Review"}
        </button>
      </div>
    );
  }

  // ---------- live progress (agent running) ----------
  const livePanel = () => {
    const lv = live || {};
    const traj = lv.trajectory || [];
    const step = lv.step || 0;
    const maxs = lv.max_steps || 0;
    const c = lv.cost || {};
    const toks = (c.prompt_tokens || 0) + (c.completion_tokens || 0);
    const paperTraces = lv.paper_traces || [];
    return (
      <div className="rv-block">
        <div className="live-head">
          <div className="spinner" />
          <div className="live-title">
            <strong>Agent working on claim {ci + 1}…</strong>
            <div className="muted">{lv.last_action || "starting up"}</div>
          </div>
          <div className="live-metrics">
            <span className="lm">
              Step {step}
              {maxs ? `/${maxs}` : ""}
            </span>
            <span className="lm">📄 {lv.examined ?? 0} examined</span>
            <span className="lm">🔀 {lv.comparisons ?? 0} compared</span>
            {(lv.retrieval_rounds ?? 0) > 0 && (
              <span className="lm">🌐 {lv.retrieval_rounds} retrieval</span>
            )}
            <span className="lm cost">
              {usd(c.usd)} · {toks.toLocaleString()} tok
            </span>
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

  // ---------- one claim: just the verified Evidence (overlapping papers first) ----------
  const claimPage = () => {
    const verify = data.verify || [];

    // overlap grouping: papers whose contribution overlaps the claim come first, worst
    // first. Both the predicate and the ordering are decided by the backend (verdict.py)
    // and arrive as `is_overlap` / `overlap_rank`.
    const isOverlap = (v) => v.is_overlap === true;
    const bySeverity = (a, b) =>
      (b.challenges === true) - (a.challenges === true) ||
      (a.overlap_rank ?? 9) - (b.overlap_rank ?? 9);
    const evOverlap = verify.filter(isOverlap).sort(bySeverity);
    const evDistinct = verify.filter((v) => !isOverlap(v));

    const evCard = (v) => {
      const overlapping = isOverlap(v);
      return (
        <div
          className={"ev-paper" + (v.challenges ? " challenges" : "")}
          key={v.paper_id}
        >
          <div className="ev-head">
            <span className="ev-title">{v.title}</span>
            {v.overlap_degree && (
              <span
                className={
                  "relbadge " +
                  (v.challenges ? "low" : overlapping ? "mid" : "high")
                }
              >
                {DEGREE_LABEL[v.overlap_degree] || v.overlap_degree}
              </span>
            )}
          </div>
          {fmtAuthors(v.authors, v.year) && (
            <div className="ev-authors">{fmtAuthors(v.authors, v.year)}</div>
          )}
          {overlapping ? (
            <>
              {v.paper_realization && v.paper_realization.length > 0 && (
                <div className="ev-realize">
                  <div className="ev-sublab">
                    How this paper realizes the claim
                  </div>
                  <Realization
                    segments={v.paper_realization}
                    docKey={"pap:" + v.paper_id}
                    activeId={reader.focusId}
                    onPick={(id) =>
                      setReader({ paperId: v.paper_id, focusId: id })
                    }
                  />
                </div>
              )}
              <EvidencePairs
                pairs={v.evidence}
                evidenceStatus={v.evidence_status}
                supportingPairIndices={v.supporting_pair_indices}
                evidenceReasoning={v.evidence_reasoning}
                paperId={v.paper_id}
                docKey={"pap:" + v.paper_id}
                activeId={reader.focusId}
                onPickSubmission={(id) =>
                  setReader({ paperId: null, focusId: id })
                }
                onPickPaper={(id) =>
                  setReader({ paperId: v.paper_id, focusId: id })
                }
              />
              <DeltaEvidence
                held={v.delta_items}
                withdrawn={v.delta_withdrawn}
              />
              <Deepening d={v.deepening} />
              {(v.assessment || v.what_is_shared || v.submission_delta) && (
                <div className="ev-assess">
                  <div className="ev-sublab">
                    Comparison with the submission
                  </div>
                  {v.assessment ? (
                    <div className="ev-analysis">{v.assessment}</div>
                  ) : (
                    <>
                      {v.what_is_shared && (
                        <div className="ev-line">
                          <span className="ev-lab">Shared:</span>{" "}
                          {v.what_is_shared}
                        </div>
                      )}
                      {v.submission_delta && (
                        <div className="ev-line">
                          <span className="ev-lab">Submission adds:</span>{" "}
                          {v.submission_delta}
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </>
          ) : (
            <div className="ev-line">
              <span className="ev-lab">Why no overlap:</span>{" "}
              {v.analysis ||
                v.assessment ||
                v.submission_delta ||
                v.what_is_shared ||
                "—"}
            </div>
          )}
          {(v.decision_trace || []).length > 0 && (
            <details className="decision-trace" open>
              <summary>Decision trace</summary>

              <div className="pt-summary">
                {v.evidence_status && (
                  <span>evidence: {v.evidence_status}</span>
                )}

                <span>{v.grounded_pairs || 0} grounded + owned pair(s)</span>

                {v.insufficient && <span>⚠ insufficient</span>}
              </div>

              {(v.decision_trace || [])
                .filter(traceImportant)
                .map((line, i) => (
                  <div className="pt-line" key={i}>
                    {prettyTrace(line)}
                  </div>
                ))}

              <details className="raw-trace" open>
                <summary>Full audit trace</summary>
                {(v.decision_trace || []).map((line, i) => (
                  <div key={i}>{line}</div>
                ))}
              </details>
            </details>
          )}
          <FulltextFetchBadge status={v.fulltext_fetch_status} />
        </div>
      );
    };

    return (
      <div className="rv-block primary">
        <div className="rv-h">
          <span className="rv-ic">🔀</span>
          <h3>Evidence</h3>
          <span className="rv-count">{verify.length}</span>
        </div>
        <p className="muted rv-sub">
          Claim-vs-paper comparison for each relevant paper. For overlapping
          papers, the narrative explains how the paper realizes the claim, with
          quotes copied verbatim from the paper and machine-verified (✓).
        </p>
        <div className="sections-legend">
          <span className="sb-ic">🗂️</span> Each deep dive adaptively reads
          selected sections of the prior paper. Verbatim evidence is then
          checked against the complete parsed documents.
        </div>
        {verify.length === 0 && (
          <div className="muted">
            No comparisons were recorded for this claim.
          </div>
        )}
        {evOverlap.length > 0 && (
          <>
            <div className="ev-group warn">
              Overlap <span className="rv-count">{evOverlap.length}</span>
            </div>
            {evOverlap.map(evCard)}
          </>
        )}
        {evDistinct.length > 0 && (
          <>
            <div className="ev-group">
              No overlap <span className="rv-count">{evDistinct.length}</span>
            </div>
            {evDistinct.map(evCard)}
          </>
        )}
      </div>
    );
  };

  // Every passage the assessment quotes from whichever document is on the right. The
  // submission is the default: it is the reviewer's own paper, and seeing all of it
  // marked at once shows which parts of the contribution the evidence actually rests on.
  // Colours run per prior paper so two papers quoted on the same claim stay apart.
  const verify = (data && data.verify) || [];
  const paperColor = {};
  verify.forEach((v, i) => {
    paperColor[v.paper_id] = colorFor(i + 1);
  });

  const readerDoc = reader.paperId
    ? verify.find((v) => v.paper_id === reader.paperId)
    : null;
  // Pair quotes are highlights too, and the submission carries the pair halves from EVERY
  // paper: the reviewer's own document is where the overlaps land, so opening it should
  // show all of them at once, each in the colour of the paper that matched it.
  const highlights = readerDoc
    ? quotesOf(
        readerDoc.paper_realization,
        "pap:" + readerDoc.paper_id,
        paperColor[readerDoc.paper_id],
      ).concat(
        pairQuotesOf(
          readerDoc.evidence,
          "pap:" + readerDoc.paper_id,
          "paper",
          paperColor[readerDoc.paper_id],
        ),
      )
    : quotesOf(data && data.claim_realization, "sub", colorFor(0)).concat(
        verify.flatMap((v) =>
          pairQuotesOf(
            v.evidence,
            `subpair:${v.paper_id}`,
            "submission",
            paperColor[v.paper_id],
          ),
        ),
      );
  const readerUrl = readerDoc
    ? api.paperPdfUrl(submissionId, readerDoc.paper_id)
    : api.pdfUrl(submissionId);
  const papersWithQuotes = verify.filter(
    (v) =>
      (v.paper_realization || []).some((x) => x.kind === "quote") ||
      (v.evidence || []).some((q) => q.paper_quote),
  );

  const viewer = (
    <div className="pdfpane">
      <div className="pdfpicker">
        <select
          value={reader.paperId || ""}
          onChange={(e) =>
            setReader({ paperId: e.target.value || null, focusId: null })
          }
        >
          <option value="">The submission (claim evidence)</option>
          {papersWithQuotes.map((v) => (
            <option key={v.paper_id} value={v.paper_id}>
              {v.title}
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

  const panel = (
    <div className="panel review-wt">
      <div className="review-head">
        <div>
          <h2>Evidence-Based Review</h2>
          <div className="muted">
            Claim {ci + 1} of {n} · {list.n_reference_papers} reference papers
          </div>
        </div>
        <div className="review-head-right">
          <PipelineCostBadge
            submissionId={submissionId}
            refreshKey={costTick}
          />
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

      <div className="claim-under-review">
        <div className="cur-label">Claim under review</div>
        <div className="cur-text">{claim.claim_text}</div>
      </div>

      {ready && data.claim_realization && data.claim_realization.length > 0 && (
        <div className="rv-block realize-block">
          <div className="rv-h sm">
            <span className="rv-ic">📝</span>
            <h4>What the submission does for this claim</h4>
          </div>
          <p className="muted rv-sub">
            Read from the submission's own sections about this contribution (not
            its results). Quotes are verbatim from your paper.
          </p>
          <Realization
            segments={data.claim_realization}
            docKey="sub"
            activeId={reader.focusId}
            onPick={(id) => setReader({ paperId: null, focusId: id })}
          />
        </div>
      )}

      {ready ? (
        <>
          {data.agent?.verdict && (
            <div
              className={
                "agent-info" +
                (!data.agent.evidence_sufficient ? " insufficient" : "")
              }
            >
              <strong>
                {data.agent.verdict === "challenged"
                  ? "Challenged by prior work"
                  : data.agent.verdict === "uncertain"
                    ? "Uncertain"
                    : "Not challenged in the examined literature"}
              </strong>

              {!data.agent.evidence_sufficient && (
                <span>Evidence remained insufficient.</span>
              )}
            </div>
          )}
          {claimPage()}
          <TimingPanel timings={data.timings} />
          <div className="review-actions split">
            <button
              className="secondary"
              disabled={loading || ci === 0}
              onClick={goPrev}
            >
              ‹ Previous claim
            </button>
            <button disabled={loading} onClick={goNext}>
              {ci < n - 1 ? "Confirm & next claim ›" : "Confirm & finish"}
            </button>
          </div>
        </>
      ) : (
        livePanel()
      )}
    </div>
  );

  return <SplitView storageKey="review" left={panel} right={viewer} />;
}
