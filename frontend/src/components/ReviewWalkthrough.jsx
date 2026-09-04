import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import PipelineCostBadge from './PipelineCostBadge.jsx'

// icon per agent tool action, for the live trajectory
const ACTION_ICON = {
  list_related_work: '📚', search_submission: '🔎', list_sections: '🗂️',
  read_paper: '📄', retrieve_more: '🌐', record_comparison: '🔀', finish: '🏁',
  triage: '⚡', triage_result: '⚡', deep_dive: '🔬',
  understand_submission: '📝', read_sections: '🗂️',
}
const usd = (v) => '$' + (Number(v || 0)).toFixed(4)

const DEGREE_LABEL = {
  same: 'same contribution', substantial: 'substantial overlap', partial: 'partial overlap',
  superficial: 'no overlap', none: 'no overlap',
}
const OVERLAP_DEGREES = ['same', 'substantial', 'partial']

// "Haoyu Han, Harry Shomer, ..." (+ year) -> "Han et al. · 2025"
function fmtAuthors(a, year) {
  const names = (a || '').split(/,\s*/).map((s) => s.trim()).filter(Boolean)
  let cite = ''
  if (names.length) {
    const first = names[0].split(/\s+/).slice(-1)[0]
    cite = names.length > 1 ? `${first} et al.` : names[0]
  }
  return [cite, year].filter(Boolean).join(' · ')
}

// A flowing explanation built from prose + verbatim quote segments. Quote segments
// (verified === true) render as a quote with a ✓ meaning "appears verbatim in the source".
function Realization({ segments }) {
  const segs = (segments || []).filter((s) => (s.content || '').trim())
  if (!segs.length) return null
  const hasQuote = segs.some((s) => s.kind === 'quote')
  return (
    <div className="realization">
      {segs.map((s, i) =>
        s.kind === 'quote' ? (
          <blockquote className="rz-quote" key={i}>
            <span className="rz-qmark" title="This quote appears verbatim in the source text">✓</span>
            <span className="rz-qtext">{s.content}</span>
          </blockquote>
        ) : (
          <p className="rz-text" key={i}>{s.content}</p>
        )
      )}
      {hasQuote && <div className="rz-legend"><span className="ok">✓</span> = quote appears verbatim in the paper</div>}
    </div>
  )
}


// Outcome of the on-demand GROBID full-text fetch for a deep-dived paper. Only
// rendered when a fetch was actually attempted (null = abstract-only triage, no
// deep dive) -- "already_had" is silent (nothing noteworthy happened).
const FT_FETCH_LABEL = {
  ok: { text: 'Full text parsed for this deep dive', cls: 'ok' },
  no_pdf: { text: 'No PDF available — compared using the abstract only', cls: 'warn' },
  parse_empty: { text: 'PDF has no extractable text (scanned) — compared using the abstract only', cls: 'warn' },
  parse_error: { text: 'PDF could not be parsed — compared using the abstract only', cls: 'warn' },
  // legacy statuses from runs before the in-process parser replaced GROBID
  grobid_unreachable: { text: 'Full-text parsing service was down — compared using the abstract only', cls: 'warn' },
  grobid_empty: { text: 'PDF could not be parsed (scanned/empty) — compared using the abstract only', cls: 'warn' },
  grobid_error: { text: 'Full-text parsing failed — compared using the abstract only', cls: 'warn' },
}
function FulltextFetchBadge({ status }) {
  const info = FT_FETCH_LABEL[status]
  if (!info) return null
  return <div className={'ft-fetch-badge ' + info.cls}>{info.cls === 'ok' ? '📄' : '⚠'} {info.text}</div>
}

// Human-readable duration: 2m 05s / 47.3s / 0.8s
const dur = (s) => {
  const v = Number(s || 0)
  if (v >= 60) { const m = Math.floor(v / 60); return `${m}m ${String(Math.round(v - m * 60)).padStart(2, '0')}s` }
  return `${v.toFixed(1)}s`
}
const PHASE_LABEL = {
  rerank: 'Rerank pool (relevance)',
  understand_submission: 'Read the submission for this claim',
  triage: 'Triage whole pool (abstracts)',
  deep_dive_total: 'Deep dives (full-text compare)',
  reentry: 'Re-entry retrieval + triage',
  other: 'Indexing / bookkeeping',
}
const PHASE_ORDER = ['rerank', 'understand_submission', 'triage', 'deep_dive_total', 'reentry', 'other']

// Wall-clock breakdown for one claim: where the time went. Almost all of it is LLM
// latency (triage + the per-paper deep-dive comparisons); PDF parsing is ~1s each.
function TimingPanel({ timings }) {
  const [open, setOpen] = useState(false)
  if (!timings || !timings.total) return null
  const total = Number(timings.total)
  const rows = PHASE_ORDER
    .filter((k) => Number(timings[k]) > 0)
    .map((k) => ({ k, label: PHASE_LABEL[k], s: Number(timings[k]) }))
    .sort((a, b) => b.s - a.s)
  const papers = timings.deep_dive_papers || []
  const slowest = rows[0]
  return (
    <div className="rv-block timing-block">
      <div className="rv-h sm timing-head" onClick={() => setOpen((o) => !o)} style={{ cursor: 'pointer' }}>
        <span className="rv-ic">⏱️</span>
        <h4>This claim took {dur(total)}</h4>
        <span className="timing-toggle">{open ? 'hide breakdown ▲' : 'show breakdown ▼'}</span>
      </div>
      {slowest && (
        <p className="muted rv-sub">
          Biggest chunk: <strong>{slowest.label}</strong> ({dur(slowest.s)}, {Math.round(100 * slowest.s / total)}%).
          {' '}This is model latency — deep-dive comparisons and pool triage dominate; PDF parsing is ~1s per paper.
        </p>
      )}
      {open && (
        <>
          <div className="timing-bars">
            {rows.map((r) => (
              <div className="timing-row" key={r.k}>
                <div className="tr-label">{r.label}</div>
                <div className="tr-bar-wrap">
                  <div className="tr-bar" style={{ width: `${Math.max(2, 100 * r.s / total)}%` }} />
                </div>
                <div className="tr-val">{dur(r.s)} · {Math.round(100 * r.s / total)}%</div>
              </div>
            ))}
          </div>
          {papers.length > 0 && (
            <div className="timing-papers">
              <div className="tp-title">Per deep-dive paper (parse vs. LLM compare)</div>
              {papers.map((p, i) => (
                <div className="tp-row" key={i}>
                  <div className="tp-name" title={p.title}>{p.title || p.paper_id}</div>
                  <div className="tp-nums">
                    <span className="tp-parse" title="PDF parsing (in-process)">parse {dur(p.parse_s)}</span>
                    <span className="tp-cmp" title="LLM comparison">compare {dur(p.compare_s)}</span>
                    <span className="tp-tot">= {dur(p.total_s)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default function ReviewWalkthrough({ submissionId, onFinish }) {
  const [list, setList] = useState(null)
  const [err, setErr] = useState('')
  const [started, setStarted] = useState(false)
  const [ci, setCi] = useState(0)
  const [cache, setCache] = useState({})     // claim_id -> computed claim data
  const [loading, setLoading] = useState(false)
  const [live, setLive] = useState(null)     // live agent progress for the current claim
  const [costTick, setCostTick] = useState(0) // bump to re-fetch the pipeline cost badge
  const pollRef = useRef(null)
  const trajRef = useRef(null)

  useEffect(() => {
    api.reviewClaims(submissionId).then(setList).catch((e) => setErr(String(e)))
    return () => clearTimeout(pollRef.current)
  }, [submissionId])

  const trajLen = live && live.trajectory ? live.trajectory.length : 0
  useEffect(() => {
    if (trajRef.current) trajRef.current.scrollTop = trajRef.current.scrollHeight
  }, [trajLen])

  if (err) return <div className="error">{err}</div>
  if (!list) return <div className="panel">Loading review…</div>

  const claims = list.claims
  const n = claims.length

  const pollLive = (id) =>
    new Promise((resolve, reject) => {
      let fails = 0
      const tick = async () => {
        let d = null
        try {
          d = await api.claimLive(submissionId, id)
          fails = 0
        } catch (e) {
          // transient network/timeout hiccup: keep polling, give up after 5 in a row
          if (++fails >= 5) { reject(e); return }
        }
        if (d) {
          setLive(d)
          // only stop on a done payload that carries the assembled review
          if (d.status === 'done' && d.review) { resolve(d); return }
          if (d.status === 'error') { reject(new Error(d.error || 'agent error')); return }
        }
        pollRef.current = setTimeout(tick, 1200)
      }
      pollRef.current = setTimeout(tick, 400)
    })

  const loadClaim = async (idx) => {
    setCi(idx); setStarted(true); window.scrollTo(0, 0)
    const id = claims[idx].claim_id
    if (cache[id]) { setLive(null); return }
    setLoading(true)
    setLive({ status: 'running', step: 0, trajectory: [], cost: { usd: 0 } })
    try {
      const resp = await api.computeClaim(submissionId, id)
      const d = resp.status === 'done' ? resp : await pollLive(id)
      if (d.review) setCache((c) => ({ ...c, [id]: d.review }))
      setCostTick((t) => t + 1)
    } catch (e) {
      setErr(String(e))
    } finally {
      setLoading(false)
    }
  }

  const claim = started ? claims[ci] : null
  const data = claim ? cache[claim.claim_id] : null
  const ready = data && !loading

  // advance to the next claim, or hand off to the Summary tab after the last one
  const goNext = async () => {
    if (ci < n - 1) await loadClaim(ci + 1)
    else if (onFinish) onFinish()
  }
  // go back to a previous (already reviewed) claim -- instant, it's cached
  const goPrev = async () => {
    if (ci > 0) await loadClaim(ci - 1)
  }

  // ---------- intro ----------
  if (!started) {
    return (
      <div className="panel review-intro">
        <div className="bot">🤖</div>
        <h2>Evidence-Based Novelty Review</h2>
        <p className="muted">{n} claims ready · {list.n_reference_papers} reference papers selected.</p>
        <p className="muted">For each claim, an agent reads the submission's own sections about the contribution, then reads the relevant prior work section by section and gathers <strong>verifiable evidence</strong> of any overlap. Claims are analysed one at a time.</p>
        <button className="begin" disabled={loading} onClick={() => loadClaim(0)}>
          {loading ? 'Analysing claim 1…' : '✨ Start Claim-Level Review'}
        </button>
      </div>
    )
  }

  // ---------- live progress (agent running) ----------
  const livePanel = () => {
    const lv = live || {}
    const traj = lv.trajectory || []
    const step = lv.step || 0
    const maxs = lv.max_steps || 0
    const c = lv.cost || {}
    const toks = (c.prompt_tokens || 0) + (c.completion_tokens || 0)
    return (
      <div className="rv-block">
        <div className="live-head">
          <div className="spinner" />
          <div className="live-title">
            <strong>Agent working on claim {ci + 1}…</strong>
            <div className="muted">{lv.last_action || 'starting up'}</div>
          </div>
          <div className="live-metrics">
            <span className="lm">Step {step}{maxs ? `/${maxs}` : ''}</span>
            <span className="lm">📄 {lv.examined ?? 0} examined</span>
            <span className="lm">🔀 {lv.comparisons ?? 0} compared</span>
            {(lv.retrieval_rounds ?? 0) > 0 && <span className="lm">🌐 {lv.retrieval_rounds} retrieval</span>}
            <span className="lm cost">{usd(c.usd)} · {toks.toLocaleString()} tok</span>
          </div>
        </div>
        {maxs > 0 && <div className="live-bar"><div className="live-fill" style={{ width: `${Math.min(100, Math.round((step / maxs) * 100))}%` }} /></div>}
        <div className="live-traj" ref={trajRef}>
          {traj.length === 0 && <div className="muted">Booting the agent…</div>}
          {traj.map((t) => (
            <div className="tr-row" key={t.step}>
              <span className="tr-ic">{ACTION_ICON[t.action] || '•'}</span>
              <span className="tr-act">{t.action}</span>
              <span className="tr-det muted">{t.detail}</span>
            </div>
          ))}
        </div>
      </div>
    )
  }

  // ---------- one claim: just the verified Evidence (overlapping papers first) ----------
  const claimPage = () => {
    const verify = data.verify || []

    // overlap grouping: papers whose contribution overlaps the claim come first, worst first
    const DEG_RANK = { same: 0, substantial: 1, partial: 2, superficial: 3, none: 4 }
    const isOverlap = (v) => v.challenges || OVERLAP_DEGREES.includes(v.overlap_degree)
    const bySeverity = (a, b) =>
      (b.challenges === true) - (a.challenges === true) ||
      (DEG_RANK[a.overlap_degree] ?? 5) - (DEG_RANK[b.overlap_degree] ?? 5)
    const evOverlap = verify.filter(isOverlap).sort(bySeverity)
    const evDistinct = verify.filter((v) => !isOverlap(v))

    const evCard = (v) => {
      const overlapping = isOverlap(v)
      return (
        <div className={'ev-paper' + (v.challenges ? ' challenges' : '')} key={v.paper_id}>
          <div className="ev-head">
            <span className="ev-title">{v.title}</span>
            {v.overlap_degree && (
              <span className={'relbadge ' + (v.challenges ? 'low' : overlapping ? 'mid' : 'high')}>
                {DEGREE_LABEL[v.overlap_degree] || v.overlap_degree}
              </span>
            )}
          </div>
          {fmtAuthors(v.authors, v.year) && <div className="ev-authors">{fmtAuthors(v.authors, v.year)}</div>}
          {overlapping ? (
            <>
              {v.paper_realization && v.paper_realization.length > 0 && (
                <div className="ev-realize">
                  <div className="ev-sublab">How this paper realizes the claim</div>
                  <Realization segments={v.paper_realization} />
                </div>
              )}
              {(v.assessment || v.what_is_shared || v.submission_delta) && (
                <div className="ev-assess">
                  <div className="ev-sublab">Comparison with the submission</div>
                  {v.assessment
                    ? <div className="ev-analysis">{v.assessment}</div>
                    : <>
                        {v.what_is_shared && <div className="ev-line"><span className="ev-lab">Shared:</span> {v.what_is_shared}</div>}
                        {v.submission_delta && <div className="ev-line"><span className="ev-lab">Submission adds:</span> {v.submission_delta}</div>}
                      </>}
                </div>
              )}
            </>
          ) : (
            <div className="ev-line"><span className="ev-lab">Why no overlap:</span> {v.analysis || v.assessment || v.submission_delta || v.what_is_shared || '—'}</div>
          )}
          <FulltextFetchBadge status={v.fulltext_fetch_status} />
        </div>
      )
    }

    return (
      <div className="rv-block primary">
        <div className="rv-h"><span className="rv-ic">🔀</span><h3>Evidence</h3><span className="rv-count">{verify.length}</span></div>
        <p className="muted rv-sub">
          Claim-vs-paper comparison for each relevant paper. For overlapping papers, the narrative explains how the paper realizes the claim, with quotes copied verbatim from the paper and machine-verified (✓).
        </p>
        <div className="sections-legend"><span className="sb-ic">🗂️</span> The blue box under a paper lists the sections that were read in full and used for the comparison.</div>
        {verify.length === 0 && <div className="muted">No comparisons were recorded for this claim.</div>}
        {evOverlap.length > 0 && (
          <>
            <div className="ev-group warn">Overlap <span className="rv-count">{evOverlap.length}</span></div>
            {evOverlap.map(evCard)}
          </>
        )}
        {evDistinct.length > 0 && (
          <>
            <div className="ev-group">No overlap <span className="rv-count">{evDistinct.length}</span></div>
            {evDistinct.map(evCard)}
          </>
        )}
      </div>
    )
  }

  return (
    <div className="panel review-wt">
      <div className="review-head">
        <div>
          <h2>Evidence-Based Review</h2>
          <div className="muted">Claim {ci + 1} of {n} · {list.n_reference_papers} reference papers</div>
        </div>
        <div className="review-head-right">
          <PipelineCostBadge submissionId={submissionId} refreshKey={costTick} />
          <div className="claim-dots">
            {claims.map((_, i) => <span key={i} className={'cdot' + (i < ci ? ' done' : i === ci ? ' current' : '')} />)}
          </div>
        </div>
      </div>

      <div className="claim-under-review">
        <div className="cur-label">Claim under review</div>
        <div className="cur-text">{claim.claim_text}</div>
      </div>

      {ready && data.claim_realization && data.claim_realization.length > 0 && (
        <div className="rv-block realize-block">
          <div className="rv-h sm"><span className="rv-ic">📝</span><h4>What the submission does for this claim</h4></div>
          <p className="muted rv-sub">Read from the submission's own sections about this contribution (not its results). Quotes are verbatim from your paper.</p>
          <Realization segments={data.claim_realization} />
        </div>
      )}

      {ready ? (
        <>
          {claimPage()}
          <TimingPanel timings={data.timings} />
          <div className="review-actions split">
            <button className="secondary" disabled={loading || ci === 0} onClick={goPrev}>
              ‹ Previous claim
            </button>
            <button disabled={loading} onClick={goNext}>
              {ci < n - 1 ? 'Confirm & next claim ›' : 'Confirm & finish'}
            </button>
          </div>
        </>
      ) : livePanel()}
    </div>
  )
}
