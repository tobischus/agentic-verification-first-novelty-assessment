import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, idempotencyKey } from '../api.js'
import { clearLocalDraft, loadLocalDraft, saveLocalDraft } from '../outbox.js'
import ReportRenderer from '../components/ReportRenderer.jsx'
import StudyPdfPane from '../components/StudyPdfPane.jsx'
import { colorFor } from '../vendor/pdf/PdfViewer.jsx'

const CRITERIA = [
  { key: 'submission_fidelity',
    q: "Which report more accurately represents the submission's contributions, methods, assumptions, and limitations?" },
  { key: 'comparison_specificity',
    q: 'Which report provides more concrete and decision-relevant comparisons with prior work?' },
  { key: 'presented_evidence',
    q: 'Which report better supports its important statements with relevant, attributable evidence or explanations?' },
  { key: 'conclusion_warrant',
    q: 'Which report better justifies its novelty judgment through its comparisons and their limitations?' },
  { key: 'reviewer_usefulness',
    q: "Which report better helps you assess the submission's novelty with reasonable effort?" },
]
const WINNERS = [
  { v: 'A', label: 'A is better' },
  { v: 'B', label: 'B is better' },
  { v: 'tie', label: 'Tie' },
  { v: 'unclear', label: 'Unclear' },
]
const UNCLEAR_REASONS = ['Insufficient report evidence', 'Insufficient domain expertise',
                         'Ambiguous criterion', 'Other']
const AUTOSAVE_MS = 2000
const wordCount = (s) => (s || '').trim().split(/\s+/).filter(Boolean).length

export default function TaskRate({ me, assignmentId, onDone, onBack, onError }) {
  const [task, setTask] = useState(null)
  const [criteria, setCriteria] = useState({})
  const [fullDescriptions, setFullDescriptions] = useState({})
  const [revision, setRevision] = useState(0)
  const [saveState, setSaveState] = useState('saved') // saved | unsaved | saving | error
  const [savedAt, setSavedAt] = useState(null)
  const [conflict, setConflict] = useState(null)
  const [reports, setReports] = useState({ a: null, b: null })
  const [showSubmission, setShowSubmission] = useState(false)
  const [focusId, setFocusId] = useState(null)
  const [familiarity, setFamiliarity] = useState({ familiarity: '', read_before: null })
  const [famNeeded, setFamNeeded] = useState(false)
  const [issueOpen, setIssueOpen] = useState(false)
  const [issueText, setIssueText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const submitKeyRef = useRef(idempotencyKey())
  const saveTimer = useRef(null)
  const readOnly = task?.status === 'submitted'

  // --- load task + both reports ------------------------------------------------- //
  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const t = await api.getTask(assignmentId)
        if (!alive) return
        setTask(t)
        setRevision(t.revision)
        setFamNeeded(!t.familiarity)
        if (t.familiarity) setFamiliarity(t.familiarity)

        const serverDraft = t.final ? t.final.criteria : (t.draft || {})
        const local = await loadLocalDraft(me.participant_id, assignmentId)
        // The server is the authority; a local draft is only offered when the server
        // has nothing (a save that never made it through) -- never silently merged over
        // a server state, which would resurrect stale text after a successful save.
        setCriteria(Object.keys(serverDraft || {}).length ? serverDraft : (local || {}))

        const load = async (rep) => {
          if (!rep) return null
          const contentUrl = api.assetUrl(rep.content_asset_id)
          if (rep.view_type === 'pdf') return { type: 'pdf', url: contentUrl }
          const text = await fetch(contentUrl, { credentials: 'same-origin' }).then((r) => r.text())
          let quoteIndex = null
          if (rep.quote_index_asset_id) {
            quoteIndex = await fetch(api.assetUrl(rep.quote_index_asset_id),
                                    { credentials: 'same-origin' }).then((r) => r.json())
          }
          return { type: 'markdown', text, quoteIndex }
        }
        const [ra, rb] = await Promise.all([load(t.report_a), load(t.report_b)])
        if (alive) setReports({ a: ra, b: rb })
      } catch (e) {
        onError(String(e.message || e))
      }
    })()
    return () => { alive = false }
  }, [assignmentId]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetch('/criteria.json').then((r) => r.json())
      .then((d) => setFullDescriptions(Object.fromEntries(d.criteria.map((c) => [c.key, c.full_description]))))
      .catch(() => {})
  }, [])

  // --- autosave ----------------------------------------------------------------- //
  const flushSave = useCallback(async (next) => {
    if (readOnly) return
    setSaveState('saving')
    try {
      const r = await api.saveDraft(assignmentId, {
        criteria: next, expected_revision: revision, idempotency_key: idempotencyKey(),
      })
      setRevision(r.revision)
      setSaveState('saved')
      setSavedAt(new Date())
      await clearLocalDraft(me.participant_id, assignmentId)
    } catch (e) {
      if (e.status === 409 && e.data && e.data.error === 'revision_conflict') {
        setConflict({ serverDraft: e.data.server_draft, serverRevision: e.data.server_revision, mine: next })
        setSaveState('error')
        return
      }
      setSaveState('error')
      await saveLocalDraft(me.participant_id, assignmentId, next)
    }
  }, [assignmentId, revision, readOnly, me.participant_id])

  const updateCriterion = (key, patch) => {
    if (readOnly) return
    const next = { ...criteria, [key]: { ...(criteria[key] || {}), ...patch } }
    setCriteria(next)
    setSaveState('unsaved')
    saveLocalDraft(me.participant_id, assignmentId, next)
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => flushSave(next), AUTOSAVE_MS)
  }

  const saveNow = () => { clearTimeout(saveTimer.current); flushSave(criteria) }

  useEffect(() => () => clearTimeout(saveTimer.current), [])

  // Warn before leaving with unsaved edits, rather than losing them silently.
  useEffect(() => {
    const handler = (e) => {
      if (saveState === 'unsaved' || saveState === 'error') { e.preventDefault(); e.returnValue = '' }
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [saveState])

  // --- validation + submit ------------------------------------------------------ //
  const problems = useMemo(() => {
    const out = []
    for (const c of CRITERIA) {
      const v = criteria[c.key] || {}
      if (!v.winner) out.push(`${c.key}: choose an option`)
      if (!(v.reason || '').trim()) out.push(`${c.key}: reason required`)
      else if (wordCount(v.reason) > 50) out.push(`${c.key}: reason is over 50 words`)
      if (v.winner === 'unclear' && !v.unclear_reason) out.push(`${c.key}: select why it is unclear`)
    }
    if (famNeeded && (!familiarity.familiarity || familiarity.read_before === null)) {
      out.push('answer the two questions about this paper')
    }
    return out
  }, [criteria, famNeeded, familiarity])

  const doSubmit = async () => {
    if (problems.length || readOnly) return
    setSubmitting(true)
    try {
      if (famNeeded) {
        await api.setFamiliarity({ paper_id: task.paper.paper_id, ...familiarity })
        setFamNeeded(false)
      }
      await flushSave(criteria)
      const r = await api.submitTask(assignmentId, {
        criteria, expected_revision: revision + 1, idempotency_key: submitKeyRef.current,
      })
      await clearLocalDraft(me.participant_id, assignmentId)
      onDone(r)
    } catch (e) {
      // A submit that raced its own autosave lands here with the current server
      // revision; re-read the task and let the participant press submit again rather
      // than silently retrying with a stale revision.
      if (e.status === 409) {
        const t = await api.getTask(assignmentId)
        setRevision(t.revision)
        onError('Your task was updated in another tab. The latest state was reloaded -- press Submit again.')
      } else {
        onError(String(e.message || e))
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (!task) return <div className="fe-page">Loading task…</div>

  const submissionHighlights = (() => {
    const seen = new Map()
    for (const rep of [reports.a, reports.b]) {
      for (const q of rep?.quoteIndex?.submission || []) if (!seen.has(q.id)) seen.set(q.id, q)
    }
    return [...seen.values()].map((q) => ({ id: q.id, text: q.text, color: colorFor(0) }))
  })()

  const openSubmissionAt = (target) => { setFocusId(target.id); setShowSubmission(true) }

  const reportPanel = (side, rep) => (
    <div className="fe-report-panel">
      <div className="fe-report-head">Report {side.toUpperCase()}</div>
      <div className="fe-report-body">
        {!rep && <div className="muted">Loading…</div>}
        {rep?.type === 'pdf' && (
          <StudyPdfPane url={rep.url} highlights={[]} title={`Report ${side.toUpperCase()} (PDF)`} />
        )}
        {rep?.type === 'markdown' && (
          <ReportRenderer text={rep.text} quoteIndex={rep.quoteIndex}
                         activeId={focusId} onPick={openSubmissionAt} />
        )}
      </div>
    </div>
  )

  return (
    <div className="fe-rate">
      <div className="fe-topbar">
        <button className="link" onClick={onBack}>‹ Task list</button>
        <div className="fe-save-state">
          {readOnly ? <span className="fe-status fe-status-submitted">Submitted (read-only)</span>
            : saveState === 'saving' ? 'Saving…'
            : saveState === 'unsaved' ? 'Unsaved changes'
            : saveState === 'error' ? <span className="fe-form-error">Connection problem — changes not yet saved</span>
            : savedAt ? `Saved at ${savedAt.toLocaleTimeString()}` : 'Saved'}
        </div>
        <div className="fe-topbar-actions">
          <button className="link" onClick={() => setShowSubmission(true)}>View submission</button>
          <button className="link" onClick={() => setIssueOpen((v) => !v)}>Report technical issue / pause</button>
        </div>
      </div>

      {conflict && (
        <div className="fe-card fe-conflict">
          <strong>This task was edited elsewhere.</strong> Your unsent edits were kept locally.
          <div className="fe-actions">
            <button onClick={async () => {
              const t = await api.getTask(assignmentId)
              setCriteria(t.draft || {}); setRevision(t.revision); setConflict(null); setSaveState('saved')
            }}>Use the server version</button>
            <button className="secondary" onClick={async () => {
              const t = await api.getTask(assignmentId)
              setRevision(t.revision); setConflict(null)
              await flushSave(conflict.mine)
            }}>Keep my version</button>
          </div>
        </div>
      )}

      {issueOpen && (
        <div className="fe-card">
          <label>Describe the problem (this is stored separately and does not affect your ratings)</label>
          <textarea value={issueText} onChange={(e) => setIssueText(e.target.value)} rows={3} />
          <button disabled={!issueText.trim()} onClick={async () => {
            await api.reportIssue({ message: issueText, assignment_id: assignmentId })
            setIssueText(''); setIssueOpen(false)
          }}>Send</button>
        </div>
      )}

      <div className="fe-reports">
        {reportPanel('a', reports.a)}
        {reportPanel('b', reports.b)}
      </div>

      <div className="fe-form fe-card">
        <h2>Your assessment</h2>

        {famNeeded && (
          <div className="fe-fam">
            <div className="fe-field">
              <label>How familiar are you with this paper's research area?</label>
              <select value={familiarity.familiarity} disabled={readOnly}
                     onChange={(e) => setFamiliarity((f) => ({ ...f, familiarity: e.target.value }))}>
                <option value="">Select…</option>
                <option value="low">Low</option>
                <option value="moderate">Moderate</option>
                <option value="high">High</option>
              </select>
            </div>
            <div className="fe-field">
              <label>Have you read this submission before?</label>
              <select value={familiarity.read_before === null ? '' : String(familiarity.read_before)}
                     disabled={readOnly}
                     onChange={(e) => setFamiliarity((f) => ({ ...f, read_before: e.target.value === 'true' }))}>
                <option value="">Select…</option>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </div>
          </div>
        )}

        {CRITERIA.map((c) => {
          const v = criteria[c.key] || {}
          const wc = wordCount(v.reason)
          return (
            <div className="fe-criterion" key={c.key}>
              <div className="fe-criterion-q">{c.q}</div>
              {fullDescriptions[c.key] && (
                <details className="fe-criterion-full">
                  <summary>Full criterion description</summary>
                  <p>{fullDescriptions[c.key]}</p>
                </details>
              )}
              <div className="fe-radios">
                {WINNERS.map((w) => (
                  <label key={w.v} className={'fe-radio' + (v.winner === w.v ? ' selected' : '')}>
                    <input type="radio" name={c.key} value={w.v} disabled={readOnly}
                          checked={v.winner === w.v}
                          onChange={() => updateCriterion(c.key, { winner: w.v })} />
                    {w.label}
                  </label>
                ))}
              </div>
              {v.winner === 'unclear' && (
                <div className="fe-field">
                  <label>Why is this unclear?</label>
                  <select value={v.unclear_reason || ''} disabled={readOnly}
                         onChange={(e) => updateCriterion(c.key, { unclear_reason: e.target.value })}>
                    <option value="">Select…</option>
                    {UNCLEAR_REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                  {v.unclear_reason === 'Other' && (
                    <input type="text" placeholder="Short explanation" value={v.unclear_other || ''}
                          disabled={readOnly}
                          onChange={(e) => updateCriterion(c.key, { unclear_other: e.target.value })} />
                  )}
                </div>
              )}
              <div className="fe-field">
                <label>Reason / decisive observation <span className="muted">(required, max 50 words)</span></label>
                <textarea rows={2} value={v.reason || ''} disabled={readOnly}
                         onBlur={saveNow}
                         onChange={(e) => updateCriterion(c.key, { reason: e.target.value })} />
                <div className={'fe-wordcount' + (wc > 50 ? ' over' : '')}>{wc}/50 words</div>
              </div>
              <div className="fe-field">
                <label>Locator <span className="muted">(optional: report/submission, page, section or line id)</span></label>
                <input type="text" value={v.locator || ''} disabled={readOnly}
                      onBlur={saveNow}
                      onChange={(e) => updateCriterion(c.key, { locator: e.target.value })} />
              </div>
            </div>
          )
        })}

        {!readOnly && (
          <div className="fe-submit-row">
            {problems.length > 0 && (
              <ul className="fe-problems">{problems.map((p, i) => <li key={i}>{p}</li>)}</ul>
            )}
            <button disabled={problems.length > 0 || submitting} onClick={doSubmit}>
              {submitting ? 'Submitting…' : 'Submit'}
            </button>
          </div>
        )}
        {readOnly && task.final && (
          <div className="fe-receipt">
            Submitted {new Date(task.final.submitted_at).toLocaleString()} — receipt{' '}
            <code>{task.final.receipt_id}</code>
          </div>
        )}
      </div>

      {showSubmission && (
        <div className="fe-overlay" onClick={(e) => { if (e.target.className === 'fe-overlay') setShowSubmission(false) }}>
          <div className="fe-overlay-inner">
            <div className="fe-overlay-head">
              <strong>Submission — {task.paper.title}</strong>
              <button className="link" onClick={() => setShowSubmission(false)}>close</button>
            </div>
            <StudyPdfPane
              url={api.assetUrl(task.paper.submission_pdf_asset_id)}
              highlights={submissionHighlights}
              focusId={focusId}
              onFocusChange={setFocusId}
              title="Submission"
            />
          </div>
        </div>
      )}
    </div>
  )
}
