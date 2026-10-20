import { useEffect, useState, useRef, useCallback } from 'react'
import { api } from './api'
import Upload from './components/Upload.jsx'
import StatusBar from './components/StatusBar.jsx'
import ClaimsReview from './components/ClaimsReview.jsx'
import PapersReview from './components/PapersReview.jsx'
import ReviewWalkthrough from './components/ReviewWalkthrough.jsx'
import ReviewSummary from './components/ReviewSummary.jsx'
import PublicationDate from './components/PublicationDate.jsx'

const TITLE = 'Towards Verification-First Agentic Novelty Assessment of Scientific Papers'
const STAGE_LABELS = {
  document_processing: 'Document processing', claim_extraction: 'Claim extraction',
  retrieval: 'Related-work retrieval', fetch_pdfs: 'Downloading PDFs',
  artifact_a: 'Evidence (Artifact A)', artifact_b: 'Assessment (Artifact B)',
  judge: 'Verification (Judge)', export: 'Report',
}
// The tabs are the navigation: all of them are shown from the start, and each one opens
// once the pipeline has produced what it shows.
const TABS = [
  { id: 'document', label: 'Document' },
  { id: 'claims', label: 'Claims' },
  { id: 'related', label: 'Related Work' },
  { id: 'review', label: 'Review' },
  { id: 'summary', label: 'Summary' },
]

function DocumentInfo({ submissionId, state }) {
  const [meta, setMeta] = useState(null)
  const claimsReady = (state?.stages_done || []).includes('claim_extraction')
  const retrievalDone = (state?.stages_done || []).includes('retrieval')
  useEffect(() => {
    if (!claimsReady) return
    api.claims(submissionId)
      .then((d) => setMeta({ title: d.title, date: d.publication_date, src: d.date_source }))
      .catch(() => {})
  }, [submissionId, claimsReady])

  return (
    <div className="panel doc-panel">
      <div className="eyebrow">Document</div>
      {meta ? (
        <>
          <div className="paper-title">{meta.title}</div>
          <PublicationDate
            submissionId={submissionId}
            date={meta.date}
            src={meta.src}
            retrievalDone={retrievalDone}
            onSaved={(v) => setMeta((m) => ({ ...m, date: v, src: 'reviewer' }))}
          />
          <p className="muted doc-note">
            Processed. Continue with the claims and the related work in the tabs above.
          </p>
        </>
      ) : (
        <p className="muted doc-note">
          <span className="dot-pulse" /> Processing the document — this view updates on its own.
        </p>
      )}
    </div>
  )
}

export default function App() {
  const [submissionId, setSubmissionId] = useState(() => localStorage.getItem('sid') || '')
  const [state, setState] = useState(null)
  const [active, setActive] = useState('document')
  // Set when the reviewer approves the related work: the review then starts on its own.
  const [reviewRequested, setReviewRequested] = useState(false)
  const prevStatus = useRef('')

  const poll = useCallback(async (sid) => {
    try { setState(await api.state(sid)) } catch { /* state may not exist yet */ }
  }, [])

  useEffect(() => {
    if (!submissionId) return
    localStorage.setItem('sid', submissionId)
    poll(submissionId)
    const iv = setInterval(() => poll(submissionId), 2500)
    return () => clearInterval(iv)
  }, [submissionId, poll])

  // Auto-advance the active tab on pipeline transitions; manual navigation in between
  // is respected (we only switch when the status actually changes).
  useEffect(() => {
    const s = state?.status
    if (!s || s === prevStatus.current) return
    prevStatus.current = s
    if (s === 'awaiting_review:claims') setActive('claims')
    else if (s === 'awaiting_review:papers') setActive('related')
    else if (s === 'completed') setActive('review')
  }, [state?.status])

  const clear = () => {
    setState(null); setActive('document'); setReviewRequested(false); prevStatus.current = ''
  }
  const onUploaded = (sid) => { setSubmissionId(sid); clear() }
  const reset = () => { localStorage.removeItem('sid'); setSubmissionId(''); clear() }
  const refresh = () => poll(submissionId)
  const startReview = () => { setReviewRequested(true); refresh() }

  const done = new Set(state?.stages_done || [])
  const status = state?.status || ''
  const avail = {
    document: true,
    claims: !!submissionId && done.has('claim_extraction'),
    related: !!submissionId && done.has('retrieval'),
    review: !!submissionId && status === 'completed',
    summary: !!submissionId && status === 'completed',
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-title">{TITLE}</div>
        <nav className="tabbar">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={'tab' + (active === t.id ? ' active' : '') + (avail[t.id] ? '' : ' disabled')}
              disabled={!avail[t.id]}
              onClick={() => setActive(t.id)}
            >
              {t.label}
            </button>
          ))}
          {submissionId && <button className="link newsub" onClick={reset}>New submission</button>}
        </nav>
      </header>

      {submissionId && status === 'failed' && (
        <div className="error">Pipeline failed — {state?.last_error}</div>
      )}

      <StatusBar state={state} stageLabels={STAGE_LABELS} />

      {/* Only the active tab is visible; the others stay mounted (hidden) so edits are
          preserved when switching back and forth. */}
      <div className="tabpane" hidden={active !== 'document'}>
        {submissionId
          ? <DocumentInfo submissionId={submissionId} state={state} />
          : <Upload onUploaded={onUploaded} />}
      </div>
      {avail.claims && (
        <div className="tabpane" hidden={active !== 'claims'}>
          <ClaimsReview submissionId={submissionId} onApproved={refresh} />
        </div>
      )}
      {avail.related && (
        <div className="tabpane" hidden={active !== 'related'}>
          <PapersReview submissionId={submissionId} status={status} onApproved={startReview} />
        </div>
      )}
      {avail.review && (
        <div className="tabpane" hidden={active !== 'review'}>
          <ReviewWalkthrough
            submissionId={submissionId}
            active={active === 'review'}
            autoStart={reviewRequested}
            onFinish={() => setActive('summary')}
          />
        </div>
      )}
      {avail.summary && (
        <div className="tabpane" hidden={active !== 'summary'}>
          <ReviewSummary submissionId={submissionId} active={active === 'summary'} />
        </div>
      )}
    </div>
  )
}
