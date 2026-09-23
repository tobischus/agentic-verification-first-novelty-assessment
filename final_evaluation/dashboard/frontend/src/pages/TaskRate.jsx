import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, idempotencyKey } from '../api.js'
import { clearLocalDraft, loadLocalDraft, saveLocalDraft } from '../outbox.js'
import ReportRenderer, { DIM, claimColor } from '../components/ReportRenderer.jsx'
import { claimOfPassages } from '../components/assessmentStyle.js'
import StudyPdfPane from '../components/StudyPdfPane.jsx'
import { colorFor } from '../vendor/pdf/PdfViewer.jsx'

// The five criteria, in form order. Their wording -- the short question and the full
// description -- comes from /criteria.json (a copy of prompts/criteria.json, synced by
// `cli build-frontend`), the same file the judge rubric is checked against; a second copy
// of the questions here once drifted from it (rubric v3: "limitations" vs "scope").
const CRITERIA = [
  { key: 'submission_fidelity' },
  { key: 'comparison_specificity' },
  { key: 'presented_evidence' },
  { key: 'conclusion_warrant' },
  { key: 'reviewer_usefulness' },
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
  const [questions, setQuestions] = useState({})
  const [revision, setRevision] = useState(0)
  const [saveState, setSaveState] = useState('saved') // saved | unsaved | saving | error
  const [savedAt, setSavedAt] = useState(null)
  const [conflict, setConflict] = useState(null)
  const [reports, setReports] = useState({ a: null, b: null })
  const [showSubmission, setShowSubmission] = useState(false)
  const [focusId, setFocusId] = useState(null)
  const [familiarity, setFamiliarity] = useState({ familiarity: '', read_before: null })
  const [famNeeded, setFamNeeded] = useState(false)
  const [famJustRecorded, setFamJustRecorded] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  // Validation is computed from the first keystroke, but only SHOWN for fields the
  // person has actually touched, or after they press Submit -- a form that lights up
  // red before anything was filled in reads as broken rather than as guidance.
  const [touched, setTouched] = useState({})
  const [submitAttempted, setSubmitAttempted] = useState(false)
  const submitKeyRef = useRef(idempotencyKey())
  const saveTimer = useRef(null)
  const formRef = useRef(null)
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
        if (e.data?.detail?.error === 'read_submission_first') {
          onError('Please read the submission for this paper first.')
          onBack()
          return
        }
        onError(String(e.message || e))
      }
    })()
    return () => { alive = false }
  }, [assignmentId]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    // no-store: a copy the browser cached before a rubric change would show the old wording
    fetch('/criteria.json', { cache: 'no-store' }).then((r) => r.json())
      .then((d) => {
        setFullDescriptions(Object.fromEntries(d.criteria.map((c) => [c.key, c.full_description])))
        setQuestions(Object.fromEntries(d.criteria.map((c) => [c.key, c.short_question])))
      })
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

  const markTouched = (key) => setTouched((t) => (t[key] ? t : { ...t, [key]: true }))

  // Persist the background answers as soon as BOTH are given, not at submit time: they
  // are not part of the criteria draft, so a reload in between used to discard them and
  // ask again. The endpoint refuses to overwrite an existing answer, so an early save
  // cannot change what a previous task on this paper already recorded.
  const saveFamiliarity = useCallback(async (next) => {
    if (readOnly || !next.familiarity || next.read_before === null) return
    try {
      await api.setFamiliarity({ paper_id: task.paper.paper_id, ...next })
      setFamNeeded(false)
      setFamJustRecorded(true)
    } catch (e) {
      onError(String(e.message || e))
    }
  }, [readOnly, task, onError])

  const updateFamiliarity = (patch) => {
    setFamiliarity((f) => {
      const next = { ...f, ...patch }
      saveFamiliarity(next)
      return next
    })
  }

  const updateCriterion = (key, patch) => {
    if (readOnly) return
    markTouched(key)
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
  // Per criterion, so a message can sit next to the field it is about instead of in one
  // list at the bottom; `problems` (the flat list) is still what gates submission.
  const fieldProblems = useMemo(() => {
    const out = {}
    for (const c of CRITERIA) {
      const v = criteria[c.key] || {}
      const msgs = []
      if (!v.winner) msgs.push('Choose A, B, Tie or Unclear.')
      if (wordCount(v.reason) > 50) msgs.push('The reason is over 50 words.')
      if (v.winner === 'unclear' && !v.unclear_reason) msgs.push('Select why this is unclear.')
      if (msgs.length) out[c.key] = msgs
    }
    return out
  }, [criteria])

  const famProblem = famNeeded && (!familiarity.familiarity || familiarity.read_before === null)
    ? 'Answer both background questions about this paper.' : null

  const problems = useMemo(() => {
    const out = Object.entries(fieldProblems).flatMap(([k, v]) => v.map((m) => `${k}: ${m}`))
    if (famProblem) out.push(famProblem)
    return out
  }, [fieldProblems, famProblem])

  const showFor = (key) => (submitAttempted || touched[key]) && fieldProblems[key]

  const doSubmit = async () => {
    if (readOnly) return
    if (problems.length) { setSubmitAttempted(true); return }
    setSubmitting(true)
    try {
      // Familiarity is saved the moment both answers are given (see saveFamiliarity);
      // this is only the belt-and-braces path for a save that failed earlier.
      if (famNeeded) await saveFamiliarity(familiarity)
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

  // Each report numbers its own quotes ("sub#0", "sub#1", ...), so the same id means a
  // different passage in report A and report B. Highlights are therefore keyed by the
  // passage TEXT (one id per distinct passage), and each panel's local ids are translated
  // to those -- a click in report B used to land on report A's passage of the same number.
  const { submissionHighlights, toGlobal } = (() => {
    const byText = new Map()
    const toGlobal = { a: new Map(), b: new Map() }
    for (const side of ['a', 'b']) {
      for (const q of reports[side]?.quoteIndex?.submission || []) {
        if (!byText.has(q.text)) byText.set(q.text, `q${byText.size}`)
        toGlobal[side].set(q.id, byText.get(q.text))
      }
    }
    // One colour per claim, as on the claim text in the panels (claimColor). Both reports
    // of a task number the paper's claims alike (same claim extraction), so a passage's
    // claim is read from whichever panel quotes it -- a claim's own anchor first, then
    // the first claim a passage is quoted under.
    const claimOf = new Map()
    for (const anchorsOnly of [true, false]) {
      for (const side of ['a', 'b']) {
        const rep = reports[side]
        if (rep?.type !== 'markdown' || !rep.quoteIndex) continue
        const anchors = new Set(Object.values(rep.quoteIndex.claim_anchors || {}).map((x) => x.id))
        for (const [local, n] of claimOfPassages(rep.text, rep.quoteIndex)) {
          const g = toGlobal[side].get(local)
          if (g && anchors.has(local) === anchorsOnly && !claimOf.has(g)) claimOf.set(g, n)
        }
      }
    }
    // Every quoted passage of both reports is marked, so the one just jumped to is drawn
    // at full strength and the rest at a pale tint of their own claim's colour.
    return {
      submissionHighlights: [...byText.entries()].map(([text, id]) => {
        const color = claimOf.has(id) ? claimColor(claimOf.get(id)) : colorFor(0)
        return { id, text, color: focusId && id !== focusId ? color + DIM : color }
      }),
      toGlobal,
    }
  })()
  // The panel compares against its own ids: give it the local id of the focused passage.
  const localActive = (side) => {
    for (const [local, global] of toGlobal[side]) if (global === focusId) return local
    return null
  }
  const openSubmissionAt = (side) => (target) => {
    setFocusId(toGlobal[side].get(target.id) || null)
    setShowSubmission(true)
  }

  const reportPanel = (side, rep) => (
    <div className="fe-report-panel">
      <div className="fe-report-head">Report {side.toUpperCase()}</div>
      <div className="fe-report-body">
        {!rep && <div className="muted">Loading…</div>}
        {rep?.type === 'pdf' && (
          <StudyPdfPane url={rep.url} highlights={[]} title={`Report ${side.toUpperCase()} (PDF)`} />
        )}
        {rep?.type === 'markdown' && (
          <ReportRenderer text={rep.text} quoteIndex={rep.quoteIndex} idPrefix={side}
                         activeId={localActive(side)} onPick={openSubmissionAt(side)} />
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

      <div className="fe-reports">
        {reportPanel('a', reports.a)}
        {reportPanel('b', reports.b)}
      </div>

      <div className="fe-form fe-card" ref={formRef} id="fe-rating-form">
        <div className="fe-form-head">
          <h2>Your assessment</h2>
          <button type="button" className="link"
                 onClick={() => document.querySelector('.fe-reports')?.scrollIntoView({ behavior: 'smooth' })}>
            ↑ Back to the reports
          </button>
        </div>

        {/* Asked once per person and paper. On any further comparison of the SAME paper
            the stored answers are carried over and shown read-only -- see
            models.PaperFamiliarity (unique on participant x paper) and the backend's
            /api/familiarity, which refuses to overwrite an existing answer. */}
        {famNeeded ? (
          <div className="fe-fam">
            <div className="fe-fam-intro muted">
              Two background questions about this paper. You will be asked these only once
              per paper — later comparisons of the same paper reuse your answers.
            </div>
            <div className="fe-field">
              <label htmlFor="fam-area">
                Before starting this study, how familiar were you with this paper’s research area?
              </label>
              <select id="fam-area" value={familiarity.familiarity} disabled={readOnly}
                     onChange={(e) => updateFamiliarity({ familiarity: e.target.value })}>
                <option value="">Select…</option>
                <option value="low">Low</option>
                <option value="moderate">Moderate</option>
                <option value="high">High</option>
              </select>
            </div>
            <div className="fe-field">
              <label htmlFor="fam-read">Had you read this submission before starting this study?</label>
              <select id="fam-read" value={familiarity.read_before === null ? '' : String(familiarity.read_before)}
                     disabled={readOnly}
                     onChange={(e) => updateFamiliarity({ read_before: e.target.value === 'true' })}>
                <option value="">Select…</option>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </div>
            {submitAttempted && famProblem && <div className="fe-field-error">{famProblem}</div>}
          </div>
        ) : familiarity.familiarity ? (
          <div className="fe-fam carried">
            <span className="fe-fam-carried-label">
              {famJustRecorded
                ? 'Background recorded for this paper (you will not be asked again):'
                : 'Background for this paper (recorded earlier):'}
            </span>{' '}
            familiarity with the research area before the study:{' '}
            <strong>{familiarity.familiarity}</strong>; had read this submission before the study:{' '}
            <strong>{familiarity.read_before ? 'yes' : 'no'}</strong>.
          </div>
        ) : null}

        {CRITERIA.map((c) => {
          const v = criteria[c.key] || {}
          const wc = wordCount(v.reason)
          return (
            <div className="fe-criterion" key={c.key}>
              <div className="fe-criterion-q">{questions[c.key] || 'Loading…'}</div>
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
                <label>Reason / decisive observation <span className="muted">(optional, max 50 words)</span></label>
                <textarea rows={2} value={v.reason || ''} disabled={readOnly}
                         onBlur={() => { markTouched(c.key); saveNow() }}
                         onChange={(e) => updateCriterion(c.key, { reason: e.target.value })} />
                <div className={'fe-wordcount' + (wc > 50 ? ' over' : '')}>{wc}/50 words</div>
              </div>
              {!readOnly && showFor(c.key) && (
                <ul className="fe-field-error">
                  {fieldProblems[c.key].map((m, mi) => <li key={mi}>{m}</li>)}
                </ul>
              )}
            </div>
          )
        })}

        {!readOnly && (
          <div className="fe-submit-row">
            {submitAttempted && problems.length > 0 && (
              <div className="fe-problems-summary">
                {problems.length} field{problems.length === 1 ? '' : 's'} still need attention —
                see the messages above.
              </div>
            )}
            <button disabled={submitting} onClick={doSubmit}>
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

      {/* Reachable from anywhere on the page without scrolling for it. */}
      {!readOnly && (
        <button type="button" className="fe-jump-form"
               onClick={() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>
          ▤ Rating form
          {submitAttempted && problems.length > 0 && <span className="fe-jump-badge">{problems.length}</span>}
        </button>
      )}

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
