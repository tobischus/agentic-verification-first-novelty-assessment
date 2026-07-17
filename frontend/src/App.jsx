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
const HEADER_STEPS = ['Upload', 'Claims', 'Related Work', 'Review']
const STAGE_LABELS = {
  document_processing: 'Document processing', claim_extraction: 'Claim extraction',
  retrieval: 'Related-work retrieval', fetch_pdfs: 'Downloading PDFs',
  artifact_a: 'Evidence (Artifact A)', artifact_b: 'Assessment (Artifact B)',
  judge: 'Verification (Judge)', export: 'Report',
}

// Which of the 4 header steps is currently active (0=Upload … 3=Review).
function currentStep(state) {
  const s = state?.status || ''
  const cps = state?.checkpoints || {}
  const done = new Set(state?.stages_done || [])
  if (s === 'completed') return 3
  if (s === 'awaiting_review:papers' || cps.papers === 'approved' || done.has('retrieval')) return 2
  if (cps.claims === 'approved') return 2
  if (s === 'awaiting_review:claims' || done.has('claim_extraction')) return 1
  return 0
}

function Stepper({ step, completed }) {
  return (
    <ol className="stepper">
      {HEADER_STEPS.map((label, i) => {
        const cls = completed || i < step ? 'done' : i === step ? 'current' : 'pending'
        return (
          <li key={label} className="stepitem">
            <span className={'chip ' + cls}>
              <span className="stepnum">{i + 1}</span>{label}
            </span>
            {i < HEADER_STEPS.length - 1 && <span className="arrow">→</span>}
          </li>
        )
      })}
    </ol>
  )
}

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
    <div className="panel">
      <div className="step-label">STEP 1</div>
      <h2>Document</h2>
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
          <p className="muted" style={{ marginTop: 12 }}>
            ✓ Document processed. Use the tabs above to review the claims and related work.
          </p>
        </>
      ) : (
        <p className="muted">Processing the document… this view updates automatically.</p>
      )}
    </div>
  )
}

export default function App() {
  const [submissionId, setSubmissionId] = useState(() => localStorage.getItem('sid') || '')
  const [state, setState] = useState(null)
  const [active, setActive] = useState('document')
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

  const onUploaded = (sid) => { setSubmissionId(sid); setState(null); setActive('document'); prevStatus.current = '' }
  const reset = () => { localStorage.removeItem('sid'); setSubmissionId(''); setState(null); setActive('document'); prevStatus.current = '' }
  const refresh = () => poll(submissionId)

  const done = new Set(state?.stages_done || [])
  const status = state?.status || ''
  const avail = {
    document: true,
    claims: !!submissionId && done.has('claim_extraction'),
    related: !!submissionId && done.has('retrieval'),
    review: status === 'completed',
    summary: status === 'completed',
  }
  const step = currentStep(state)
  const tabs = [
    { id: 'document', label: 'Document' },
    { id: 'claims', label: 'Claims' },
    { id: 'related', label: 'Related Work' },
    ...(avail.review ? [{ id: 'review', label: 'Review' }] : []),
    ...(avail.summary ? [{ id: 'summary', label: 'Summary' }] : []),
  ]

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-title">{TITLE}</div>
        <Stepper step={step} completed={status === 'completed'} />
      </header>
      <hr className="header-rule" />

      {submissionId && (
        <nav className="tabbar">
          {tabs.map((t) => (
            <button
              key={t.id}
              className={'tab' + (active === t.id ? ' active' : '') + (avail[t.id] ? '' : ' disabled')}
              disabled={!avail[t.id]}
              onClick={() => setActive(t.id)}
            >
              {t.label}
            </button>
          ))}
          <button className="link newsub" onClick={reset}>new submission</button>
        </nav>
      )}

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
          <PapersReview submissionId={submissionId} status={status} onApproved={refresh} />
        </div>
      )}
      {avail.review && (
        <div className="tabpane" hidden={active !== 'review'}>
          <ReviewWalkthrough submissionId={submissionId} onFinish={() => setActive('summary')} />
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
