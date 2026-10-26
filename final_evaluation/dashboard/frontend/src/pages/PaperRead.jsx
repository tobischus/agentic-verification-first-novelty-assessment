import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import StudyPdfPane from '../components/StudyPdfPane.jsx'

export default function PaperRead({ paperId, onDone, onBack, onError }) {
  const [view, setView] = useState(null)
  const [fam, setFam] = useState({ familiarity: '', read_before: null })
  const [famSaved, setFamSaved] = useState(false)
  const [checked, setChecked] = useState(false)
  const [busy, setBusy] = useState(false)
  const activeMs = useRef(0)

  useEffect(() => {
    let alive = true
    api
      .openReading(paperId)
      .then((v) => {
        if (!alive) return
        setView(v)
        if (v.familiarity) {
          setFam(v.familiarity)
          setFamSaved(true)
        }
        if (v.reading?.confirmed_at) setChecked(true)
      })
      .catch((e) => onError(String(e.message || e)))
    return () => {
      alive = false
    }
  }, [paperId])

  useEffect(() => {
    let last = Date.now()
    const t = setInterval(() => {
      const now = Date.now()
      if (!document.hidden && document.hasFocus()) activeMs.current += Math.min(now - last, 5000)
      last = now
    }, 1000)
    return () => clearInterval(t)
  }, [])

  const answer = async (patch) => {
    const next = { ...fam, ...patch }
    setFam(next)
    if (famSaved || !next.familiarity || next.read_before === null) return
    try {
      await api.setFamiliarity({ paper_id: paperId, ...next })
      setFamSaved(true)
    } catch (e) {
      onError(String(e.message || e))
    }
  }

  const confirm = async () => {
    setBusy(true)
    try {
      await api.confirmReading(paperId, { active_ms: Math.round(activeMs.current) })
      onDone()
    } catch (e) {
      onError(String(e.message || e))
    } finally {
      setBusy(false)
    }
  }

  if (!view) return <div className="fe-page">Loading…</div>
  const confirmed = !!view.reading?.confirmed_at

  return (
    <div className="fe-read">
      <div className="fe-topbar">
        <button className="link" onClick={onBack}>
          ‹ Task list
        </button>
        <div className="fe-read-title">{view.paper.title}</div>
        <div />
      </div>

      <div className="fe-card fe-read-intro">
        <h1>Before the comparisons: the submission</h1>
        <p className="muted">
          Both comparison tasks for this paper open after this step. Answer the two background
          questions, then read or skim the submission. You can open it again at any time from within
          a task.
        </p>

        <div className="fe-fam">
          <div className="fe-field">
            <label htmlFor="read-fam-area">
              Before starting this study, how familiar were you with this paper’s research area?
            </label>
            <select
              id="read-fam-area"
              value={fam.familiarity}
              disabled={famSaved}
              onChange={(e) => answer({ familiarity: e.target.value })}
            >
              <option value="">Select…</option>
              <option value="low">Low</option>
              <option value="moderate">Moderate</option>
              <option value="high">High</option>
            </select>
          </div>
          <div className="fe-field">
            <label htmlFor="read-fam-read">
              Had you read this submission before starting this study?
            </label>
            <select
              id="read-fam-read"
              disabled={famSaved}
              value={fam.read_before === null ? '' : String(fam.read_before)}
              onChange={(e) => answer({ read_before: e.target.value === 'true' })}
            >
              <option value="">Select…</option>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </div>
          {famSaved && (
            <div className="fe-fam-intro muted">
              Recorded — you will not be asked again for this paper.
            </div>
          )}
        </div>
      </div>

      {famSaved ? (
        <>
          <div className="fe-read-pdf">
            <StudyPdfPane
              url={api.assetUrl(view.paper.submission_pdf_asset_id)}
              highlights={[]}
              title="Submission"
            />
          </div>
          <div className="fe-card fe-read-confirm">
            {confirmed ? (
              <>
                <span className="muted">You confirmed reading this submission.</span>
                <button onClick={onDone}>Back to the tasks</button>
              </>
            ) : (
              <>
                <label className="fe-checkbox">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => setChecked(e.target.checked)}
                  />
                  <span>I have read or skimmed the submission.</span>
                </label>
                <button disabled={!checked || busy} onClick={confirm}>
                  {busy ? 'Saving…' : 'Continue to the tasks'}
                </button>
              </>
            )}
          </div>
        </>
      ) : (
        <div className="fe-card muted fe-read-wait">
          The submission appears here once both questions are answered.
        </div>
      )}
    </div>
  )
}
