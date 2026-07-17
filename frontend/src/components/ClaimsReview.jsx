import { useEffect, useState } from 'react'
import { api } from '../api'
import PublicationDate from './PublicationDate.jsx'
import PipelineCostBadge from './PipelineCostBadge.jsx'

// Checkpoint 1: claims shown as readable cards; hover a card for the edit (pencil) icon.
export default function ClaimsReview({ submissionId, onApproved }) {
  const [doc, setDoc] = useState(null)
  const [claims, setClaims] = useState(null)
  const [open, setOpen] = useState({})       // evidence expanded
  const [editing, setEditing] = useState({}) // claim in edit mode
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.claims(submissionId).then((d) => {
      setDoc(d)
      setClaims(d.claims
        .filter((c) => c.status !== 'rejected')
        .map((c) => ({ ...c, _key: c.id, _dirty: false, _rejected: false })))
    }).catch((e) => setErr(String(e)))
  }, [submissionId])

  const update = (key, val) =>
    setClaims((cs) => cs.map((c) => (c._key === key ? { ...c, claim_text: val, _dirty: true } : c)))
  const toggleReject = (key) =>
    setClaims((cs) => cs.map((c) => (c._key === key ? { ...c, _rejected: !c._rejected } : c)))
  const toggleOpen = (key) => setOpen((o) => ({ ...o, [key]: !o[key] }))
  const toggleEdit = (key) => setEditing((e) => ({ ...e, [key]: !e[key] }))
  const addClaim = () => {
    const key = 'new-' + Date.now()
    setClaims((cs) => [...cs, {
      _key: key, id: null, claim_text: '', evidence_quote: '', source: 'reviewer',
      _new: true, _dirty: true, _rejected: false,
    }])
    setEditing((e) => ({ ...e, [key]: true }))
  }

  const approve = async () => {
    setBusy(true); setErr('')
    try {
      const ops = []
      for (const c of claims) {
        const text = (c.claim_text || '').trim()
        if (c._new) {
          if (text) ops.push({ op: 'add', name: text.split(/\s+/).slice(0, 12).join(' '), claim_text: text })
        } else if (c._rejected) {
          ops.push({ op: 'delete', claim_id: c.id })
        } else if (c._dirty) {
          ops.push({ op: 'edit', claim_id: c.id, claim_text: text })
        }
      }
      if (ops.length) await api.editClaims(submissionId, ops)
      await api.approve(submissionId, 'claims')
      onApproved()
    } catch (e) {
      setErr(String(e)); setBusy(false)
    }
  }

  if (err && !claims) return <div className="error">{err}</div>
  if (!claims) return <div className="panel">Loading claims…</div>

  return (
    <div className="panel checkpoint">
      <div className="paper-head">
        <div className="paper-head-row">
          <div className="paper-title">{doc?.title || submissionId}</div>
          <PipelineCostBadge submissionId={submissionId} />
        </div>
        <PublicationDate
          submissionId={submissionId}
          date={doc?.publication_date}
          src={doc?.date_source}
          onSaved={(v) => setDoc((d) => ({ ...d, publication_date: v, date_source: 'reviewer' }))}
        />
      </div>

      {claims.map((c) => (
        <div key={c._key} className={'claim card' + (c._rejected ? ' rejected' : '')}>
          {!editing[c._key] && (
            <button className="edit-btn" title="Edit claim" onClick={() => toggleEdit(c._key)}>✎</button>
          )}
          {editing[c._key] ? (
            <textarea
              className="claim-text" rows={3} autoFocus value={c.claim_text}
              placeholder="novelty claim"
              onChange={(e) => update(c._key, e.target.value)}
              onBlur={() => toggleEdit(c._key)}
            />
          ) : (
            <div className="claim-body" onDoubleClick={() => toggleEdit(c._key)}>
              {c.claim_text || <span className="muted">(empty — click ✎ to edit)</span>}
            </div>
          )}
          <div className="claim-actions">
            {!c._new && c.evidence_quote && (
              <button className="link" onClick={() => toggleOpen(c._key)}>
                {open[c._key] ? '▾ hide evidence' : '▸ show evidence'}
              </button>
            )}
            {c._new && <span className="badge">new</span>}
            {!c._new && (
              <button className="link danger" onClick={() => toggleReject(c._key)}>
                {c._rejected ? 'undo remove' : 'remove'}
              </button>
            )}
          </div>
          {open[c._key] && c.evidence_quote && (
            <blockquote className="evidence">
              “{c.evidence_quote}”
              <div className="evidence-meta">
                {c.source ? `— ${c.source} ` : ''}
                {c.evidence_verified
                  ? <span className="verified">✓ verbatim in paper</span>
                  : <span className="unverified">⚠ not verbatim-matched</span>}
              </div>
            </blockquote>
          )}
        </div>
      ))}

      <div className="actions">
        <button className="secondary" onClick={addClaim}>+ add claim</button>
        <button disabled={busy} onClick={approve}>{busy ? 'Submitting…' : 'Approve & continue'}</button>
      </div>
      {err && <div className="error">{err}</div>}
    </div>
  )
}
