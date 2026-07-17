import { useState } from 'react'
import { api } from '../api'

const SRC_NOTE = {
  today_fallback: ' — no date found, using today',
  arxiv_v1: ' — arXiv v1',
  reviewer: ' — set by you',
}

// Publication-date line with HITL edit. The date is the retrieval cutoff (what counts
// as prior work), so the reviewer can correct it when the automatic lookup fails
// (e.g. a paper renamed since its arXiv version is unfindable by title).
export default function PublicationDate({ submissionId, date, src, onSaved, retrievalDone }) {
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  const save = async () => {
    setSaving(true); setErr('')
    try {
      await api.setDate(submissionId, val)
      setEditing(false)
      if (onSaved) onSaved(val)
    } catch (e) {
      setErr(String(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div className="paper-date muted">
        Publication date (retrieval cutoff): <strong>{date || '—'}</strong>
        {SRC_NOTE[src] || ''}
        {!editing && (
          <button className="link" style={{ marginLeft: 10 }}
            onClick={() => { setVal(date || ''); setEditing(true) }}>
            ✎ edit
          </button>
        )}
      </div>
      {src === 'today_fallback' && !editing && (
        <div className="date-warn">
          ⚠ The date could not be resolved automatically (e.g. the paper was renamed since
          its arXiv version). Please set the date of <strong>first public disclosure</strong>{' '}
          (arXiv v1) — it decides what counts as prior work.
        </div>
      )}
      {editing && (
        <div className="date-edit">
          <input type="date" value={val} onChange={(e) => setVal(e.target.value)} />
          <button disabled={saving || !val} onClick={save}>{saving ? 'Saving…' : 'Save'}</button>
          <button className="link" onClick={() => { setEditing(false); setErr('') }}>cancel</button>
          {retrievalDone && (
            <span className="muted date-note">
              Note: related-work retrieval already ran with the old cutoff — re-upload to re-retrieve.
            </span>
          )}
          {err && <span className="date-err">{err}</span>}
        </div>
      )}
    </>
  )
}
