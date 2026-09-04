import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'

const DEGREE_LABEL = {
  same: 'same contribution', substantial: 'substantial overlap', partial: 'partial overlap',
  superficial: 'no overlap', none: 'no overlap',
}

// Artifact B's per-claim verdict. `uncertain` exists in the schema but the agent never
// emits it today; it is rendered anyway so an old artifact does not fall through blank.
const VERDICT = {
  challenged: { label: 'challenged by prior work', cls: 'low' },
  not_challenged: { label: 'not challenged in the examined literature', cls: 'mid' },
  uncertain: { label: 'uncertain', cls: 'mid' },
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
  const [busy, setBusy] = useState(false)
  const [genErr, setGenErr] = useState('')

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

  // Builds Artifact B from Artifact A and runs the provenance audit, then reloads so the
  // whole page reflects one artifact rather than a mix of loaded and just-returned state.
  const generate = async () => {
    setBusy(true); setGenErr('')
    try {
      await api.generateConclusion(submissionId)
      load()
    } catch (e) {
      setGenErr(String(e))
    } finally {
      setBusy(false)
    }
  }

  if (err) return <div className="panel"><div className="error">{err}</div></div>
  if (!data) return <div className="panel">Loading summary…</div>

  const claims = data.claims || []
  const ready = !!data.assessment_ready
  const judge = data.judge
  const inconsistent = (judge?.deterministic_per_claim || []).filter((c) => !c.consistent).length
  const unsupported = (judge?.prose_entailment?.unsupported_statements || []).length

  return (
    <div className="panel review-summary">
      <div className="review-head">
        <div>
          <h2>Novelty Assessment</h2>
          <div className="muted">
            {data.n_claims} claim{data.n_claims === 1 ? '' : 's'}
            {' · '}{data.n_overlap_papers} overlapping {data.n_overlap_papers === 1 ? 'paper' : 'papers'}
            {ready ? ' · assessment generated' : ' · assessment not generated yet'}
          </div>
        </div>
      </div>
      <p className="muted rv-sub">
        The complete output of this review. The assessment is synthesized strictly from the
        claim-level evidence below — every statement about prior work traces back to a comparison
        whose quotes were machine-verified on both sides.
      </p>

      {claims.length === 0 && (
        <div className="muted">No claims have been reviewed yet. Open the <strong>Review</strong> tab and run the claim-level review first.</div>
      )}

      {claims.length > 0 && (
        <div className="sum-conclusion">
          <div className="rv-h sm"><span className="rv-ic">🧭</span><h4>Overall assessment</h4></div>
          {ready ? (
            <>
              <p className="conclusion-text">{data.overall_assessment}</p>
              {judge && (
                <div className="conclusion-foot">
                  <span className="muted">
                    {inconsistent === 0 && unsupported === 0
                      ? '✓ Provenance audit passed — every statement traces back to the evidence'
                      : [inconsistent > 0 && `⚠ ${inconsistent} claim${inconsistent === 1 ? '' : 's'} inconsistent with the evidence`,
                         unsupported > 0 && `${unsupported} unsupported statement${unsupported === 1 ? '' : 's'}`]
                          .filter(Boolean).join(' · ')}
                  </span>
                  <button className="link" disabled={busy} onClick={generate}>
                    {busy ? 'Regenerating…' : '↻ regenerate'}
                  </button>
                </div>
              )}
            </>
          ) : (
            <>
              <p className="muted rv-sub">
                Not generated yet. This is the last step of the review and the output that gets
                compared against other systems.
              </p>
              <button className="begin sm" disabled={busy} onClick={generate}>
                {busy ? 'Writing the assessment…' : '✨ Generate assessment'}
              </button>
            </>
          )}
          {genErr && <div className="error">{genErr}</div>}
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
                    <SectionsBox sections={o.sections_used} />
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
