import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'

const DEGREE_LABEL = {
  same: 'same contribution', substantial: 'substantial overlap', partial: 'partial overlap',
  superficial: 'no overlap', none: 'no overlap',
}

// The sections that were read in full to back a comparison (blue box) -- same as in
// the Review tab, so the summary shows exactly which sections a context came from.
function SectionsBox({ sections }) {
  const listx = (sections || []).filter(Boolean)
  if (!listx.length) return null
  return (
    <div className="sections-box">
      <span className="sb-ic">🗂️</span>
      <span className="sb-label">Sections used:</span>
      <span className="sb-list">{listx.join(' · ')}</span>
    </div>
  )
}

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
  const [concl, setConcl] = useState(null)     // { text, generated_at } | { text: null }
  const [conclBusy, setConclBusy] = useState(false)
  const [conclErr, setConclErr] = useState('')

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
    api.reviewConclusion(submissionId).then(setConcl).catch(() => {})
  }, [submissionId])

  useEffect(() => { load() }, [load])
  // refresh whenever the tab becomes active (e.g. right after finishing the review)
  useEffect(() => { if (active) load() }, [active, load])

  const genConclusion = async () => {
    setConclBusy(true); setConclErr('')
    try {
      const d = await api.generateConclusion(submissionId)
      setConcl(d)
    } catch (e) {
      setConclErr(String(e))
    } finally {
      setConclBusy(false)
    }
  }

  if (err) return <div className="panel"><div className="error">{err}</div></div>
  if (!data) return <div className="panel">Loading summary…</div>

  const claims = data.claims || []
  return (
    <div className="panel review-summary">
      <div className="review-head">
        <div>
          <h2>Review Summary</h2>
          <div className="muted">
            Overlapping prior work across {data.n_claims} claim{data.n_claims === 1 ? '' : 's'}
            {' · '}{data.n_overlap_papers} overlap {data.n_overlap_papers === 1 ? 'paper' : 'papers'}
          </div>
        </div>
      </div>
      <p className="muted rv-sub">
        The most relevant contexts gathered during the claim-level review: for each claim, only the prior
        work that overlaps the claimed contribution, with the machine-verified comparison. This summarizes
        the evidence — it does not pass a novelty verdict.
      </p>

      {claims.length === 0 && (
        <div className="muted">No claims have been reviewed yet. Open the <strong>Review</strong> tab and run the claim-level review first.</div>
      )}

      {claims.map((c) => (
        <div className="sum-claim" key={c.claim_id}>
          <div className="sum-claim-head">
            <span className="sum-claim-tag">{claimLabel(c.claim_id)}</span>
            <span className="sum-claim-text">{c.claim_text}</span>
          </div>
          {c.overlaps.length === 0 ? (
            <div className="sum-none">No overlapping prior work found for this claim ({c.n_compared} papers compared).</div>
          ) : (
            <div className="sum-overlaps">
              <div className="sum-ov-count">{c.overlaps.length} overlapping paper{c.overlaps.length === 1 ? '' : 's'}</div>
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
                  <SectionsBox sections={o.sections_used} />
                </div>
              ))}
            </div>
          )}
        </div>
      ))}

      {claims.length > 0 && (
        <div className="sum-conclusion">
          <div className="rv-h sm"><span className="rv-ic">🧭</span><h4>Overall novelty assessment</h4></div>
          <p className="muted rv-sub">
            A concluding synthesis of the evidence above, generated by an LLM strictly from the gathered
            claim-level comparisons (cited prior work, shared content, and what the submission adds). It is a
            summary of the evidence, not an editorial decision — read it critically.
          </p>
          {concl && concl.text ? (
            <>
              <p className="conclusion-text">{concl.text}</p>
              <div className="conclusion-foot">
                <span className="muted">{concl.generated_at ? `Generated ${concl.generated_at}` : ''}{concl.model ? ` · ${concl.model}` : ''}</span>
                <button className="link" disabled={conclBusy} onClick={genConclusion}>
                  {conclBusy ? 'Regenerating…' : '↻ regenerate'}
                </button>
              </div>
            </>
          ) : (
            <button className="begin sm" disabled={conclBusy} onClick={genConclusion}>
              {conclBusy ? 'Writing the overall assessment…' : '✨ Generate overall assessment'}
            </button>
          )}
          {conclErr && <div className="error">{conclErr}</div>}
        </div>
      )}
    </div>
  )
}
