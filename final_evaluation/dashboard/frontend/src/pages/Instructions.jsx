import { useEffect, useState } from 'react'
import { api } from '../api.js'

// The instructions TEXT itself lives on the server (prompts/human_instructions.md,
// PROTOCOL.md section 8's verbatim text) and is fetched, not duplicated here, so there
// is exactly one copy of it to keep in sync with the consent hash the server records.
export default function Instructions({ me, onConsented, onLogout }) {
  const [text, setText] = useState('')
  const [sha, setSha] = useState('')
  const [understood, setUnderstood] = useState(false)
  const [agree, setAgree] = useState(false)
  const [experience, setExperience] = useState('')
  const [involvement, setInvolvement] = useState('')
  const [involvementNote, setInvolvementNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    fetch('/instructions.txt', { cache: 'no-store' }).then((r) => r.text()).then(async (t) => {
      setText(t)
      const enc = new TextEncoder().encode(t)
      const digest = await crypto.subtle.digest('SHA-256', enc)
      setSha(Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, '0')).join(''))
    })
  }, [])

  const submit = async () => {
    if (!understood || !agree || !experience || !involvement) return
    setBusy(true); setErr('')
    try {
      await api.consent({
        accept: true, instructions_sha256: sha,
        review_experience: experience, system_involvement: involvement,
        system_involvement_note: involvementNote,
      })
      onConsented()
    } catch (e) {
      setErr(String(e.message || e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fe-page">
      <div className="fe-card fe-instructions">
        <h1>Before you begin</h1>
        <pre className="fe-instructions-text">{text || 'Loading…'}</pre>

        <div className="fe-practice-note">
          How it works: for each paper you first read (or skim) the submission, then
          compare its reports in that paper's comparison tasks. Your answers are saved as
          you go; you can stop at any time and continue later with the same access code.
        </div>

        <label className="fe-checkbox">
          <input type="checkbox" checked={understood} onChange={(e) => setUnderstood(e.target.checked)} />
          I have read and understood the instructions above.
        </label>
        <label className="fe-checkbox">
          <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
          I agree that my pseudonymised ratings may be used for this master's thesis research.
        </label>

        <div className="fe-field">
          <label>Review experience</label>
          <select value={experience} onChange={(e) => setExperience(e.target.value)}>
            <option value="">Select…</option>
            <option value="none">None</option>
            <option value="1-5">1–5 reviews</option>
            <option value="5+">More than 5 reviews</option>
          </select>
        </div>

        <div className="fe-field">
          <label>Were you involved in building any of the systems being evaluated?</label>
          <select value={involvement} onChange={(e) => setInvolvement(e.target.value)}>
            <option value="">Select…</option>
            <option value="yes">Yes</option>
            <option value="no">No</option>
            <option value="prefer_not">Prefer not to say</option>
          </select>
          {involvement === 'yes' && (
            <textarea placeholder="Optional note (kept private, not shown to other participants)"
                     value={involvementNote} onChange={(e) => setInvolvementNote(e.target.value)} />
          )}
        </div>

        {err && <div className="fe-form-error">{err}</div>}
        <div className="fe-actions">
          <button className="secondary" onClick={onLogout}>Log out</button>
          <button disabled={busy || !understood || !agree || !experience || !involvement} onClick={submit}>
            {busy ? 'Saving…' : 'Continue'}
          </button>
        </div>
      </div>
    </div>
  )
}
