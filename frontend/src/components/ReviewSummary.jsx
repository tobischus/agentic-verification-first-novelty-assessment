import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { DEGREE_LABEL, VERDICT } from '../verdict'



const claimLabel = (id) => (/^claim_\d+$/.test(id || '') ? id.replace('claim_', 'Claim ') : id)

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

export default function ReviewSummary({ submissionId, active }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  const [exportText, setExportText] = useState(null)   // null = hidden
  const [exportBusy, setExportBusy] = useState(false)

  const load = useCallback(() => {
    api.reviewSummary(submissionId)
      .then((d) => { setData(d); setErr('') })
      .catch((e) => {
        const msg = String(e)
        // not-yet-reviewed is an empty summary, not an error
        if (msg.includes('no claims computed') || msg.includes('404')) {
          setData({ claims: [], n_claims: 0, n_overlap_papers: 0 }); setErr('')
        } else setErr(msg)
      })
  }, [submissionId])

  useEffect(() => { load() }, [load])
  // refresh whenever the tab becomes active (e.g. right after finishing the review)
  useEffect(() => { if (active) load() }, [active, load])

  // The synthesised overall assessment is not shown here. It is prose ABOUT the review
  // rather than the review, and what a reviewer -- or a judge comparing systems -- has to
  // be able to check is the claim-level evidence below. The pipeline still builds it
  // (Artifact B), so bringing it back is a matter of rendering it again.

  // Fetches the plain-text export once and keeps it, so toggling it open and shut does
  // not hit the backend again -- the text is deterministic for a given run anyway.
  const toggleExport = async () => {
    if (exportText !== null) { setExportText(null); return }
    setExportBusy(true); setGenErr('')
    try {
      setExportText(await api.reviewExport(submissionId))
    } catch (e) {
      setGenErr(String(e))
    } finally {
      setExportBusy(false)
    }
  }

  const downloadExport = async () => {
    setExportBusy(true); setGenErr('')
    try {
      const text = exportText ?? await api.reviewExport(submissionId)
      setExportText(text)
      const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown;charset=utf-8' }))
      const a = document.createElement('a')
      a.href = url
      a.download = `${submissionId}_assessment.md`
      document.body.appendChild(a); a.click(); a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      setGenErr(String(e))
    } finally {
      setExportBusy(false)
    }
  }

  if (err) return <div className="panel"><div className="error">{err}</div></div>
  if (!data) return <div className="panel">Loading summary…</div>

  const claims = data.claims || []
  // What this review produced: pairs whose two halves were each checked against their
  // own document. The header used to report whether a synthesis had been written,
  // which said nothing about whether anything was found.
  const nPairs = claims.reduce(
    (n, c) => n + (c.overlaps || []).reduce((m, o) => m + (o.evidence || []).length, 0), 0)

  return (
    <div className="panel review-summary">
      <div className="review-head">
        <div>
          <h2>Novelty Assessment</h2>
          <div className="muted">
            {data.n_claims} claim{data.n_claims === 1 ? '' : 's'}
            {' · '}{data.n_overlap_papers} overlapping {data.n_overlap_papers === 1 ? 'paper' : 'papers'}
            {' · '}{nPairs} verified {nPairs === 1 ? 'pair' : 'pairs'}
          </div>
        </div>
      </div>
      <p className="muted rv-sub">
        The complete output of this review: for every claim, the prior work that overlaps it and
        the sentences the two papers share — each side quoted from its own document and checked
        against it automatically.
      </p>

      {claims.length === 0 && (
        <div className="muted">No claims have been reviewed yet. Open the <strong>Review</strong> tab and run the claim-level review first.</div>
      )}

      {claims.length > 0 && (
        <div className="sum-export">
          <div className="sum-export-bar">
            <span className="muted">
              Text output used for the comparison against other systems
            </span>
            <span className="sum-export-btns">
              <button className="link" disabled={exportBusy} onClick={toggleExport}>
                {exportBusy ? 'Loading…' : exportText !== null ? 'hide' : 'show'}
              </button>
              <button className="link" disabled={exportBusy} onClick={downloadExport}>
                download .md
              </button>
            </span>
          </div>
          {exportText !== null && <pre className="sum-export-text">{exportText}</pre>}
        </div>
      )}

      {claims.map((c) => {
        const v = VERDICT[c.verdict] || null
        return (
          <div className="sum-claim" key={c.claim_id}>
            <div className="sum-claim-head">
              <span className="sum-claim-tag">{claimLabel(c.claim_id)}</span>
              <span className="sum-claim-text">{c.claim_text}</span>
            </div>

            {v && (
              <div className="sum-verdict">
                <span className={'relbadge ' + v.cls}>{v.label}</span>
                {c.rationale && <p className="sum-rationale">{c.rationale}</p>}
              </div>
            )}

            {c.overlaps.length === 0 ? (
              <div className="sum-none">No overlapping prior work found for this claim ({c.n_compared} papers compared).</div>
            ) : (
              <div className="sum-overlaps">
                <div className="sum-ov-count">
                  Evidence: {c.overlaps.length} overlapping paper{c.overlaps.length === 1 ? '' : 's'} of {c.n_compared} compared
                </div>
                {c.overlaps.map((o) => (
                  <div className={'sum-paper' + (o.challenges ? ' challenges' : '')} key={o.paper_id}>
                    <div className="ev-head">
                      <span className="ev-title">{o.title}</span>
                      <span className={'relbadge ' + (o.challenges ? 'low' : 'mid')}>
                        {DEGREE_LABEL[o.overlap_degree] || o.overlap_degree}
                      </span>
                      {o.cited_by_submission && <span className="citedbadge">cited</span>}
                    </div>
                    {fmtAuthors(o.authors, o.year) && <div className="ev-authors">{fmtAuthors(o.authors, o.year)}</div>}
                    {o.assessment
                      ? <div className="ev-analysis">{o.assessment}</div>
                      : <>
                          {o.what_is_shared && <div className="ev-line"><span className="ev-lab">Shared:</span> {o.what_is_shared}</div>}
                          {o.submission_delta && <div className="ev-line"><span className="ev-lab">Submission adds:</span> {o.submission_delta}</div>}
                        </>}
                    {(o.evidence || []).length > 0 && (
                      <div className="ev-pairs">
                        <div className="ev-sublab">
                          Where the two papers say the same thing
                          <span className="ev-pairhint"> · {o.evidence.length} verified
                            {o.evidence.length === 1 ? ' pair' : ' pairs'}</span>
                        </div>
                        {o.evidence.map((q, i) => (
                          <div className="ev-pair" key={i}>
                            {q.rationale && <div className="ev-pairwhy">{q.rationale}</div>}
                            <blockquote className="rz-quote pair-sub">
                              <span className="rz-qmark" title="Verified verbatim in the submission">✓</span>
                              <span className="ev-pairside">Your paper</span>
                              <span className="rz-qtext">{q.claim_quote}</span>
                            </blockquote>
                            <blockquote className="rz-quote pair-pap">
                              <span className="rz-qmark" title="Verified verbatim in the prior paper">✓</span>
                              <span className="ev-pairside">This paper</span>
                              <span className="rz-qtext">{q.paper_quote}</span>
                            </blockquote>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
