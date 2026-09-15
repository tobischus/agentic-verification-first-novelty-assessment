import { useEffect, useState } from 'react'
import { api } from '../api.js'

// No system names, no study framing beyond the code field itself -- PROTOCOL.md section
// 8 ("Keine Systemnamen auf der Loginseite"). The contact field's address comes from
// /api/me AFTER login (it needs no auth), so a not-yet-logged-in visitor with a login
// problem still has somewhere to go; if STUDY_CONTACT is unset the backend already
// refused to start in production (settings.py), so this can only be empty in local dev.
export default function Login({ onLoggedIn }) {
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [contact, setContact] = useState('')

  useEffect(() => {
    fetch('/api/public/config').then((r) => r.json()).then((d) => setContact(d.study_contact || ''))
      .catch(() => {})
  }, [])

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setErr('')
    try {
      await api.login(code.trim())
      onLoggedIn()
    } catch (e2) {
      setErr(e2.status === 429 ? 'Too many attempts. Please wait a few minutes and try again.'
        : 'Invalid access code.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fe-center">
      <form className="fe-card fe-login" onSubmit={submit}>
        <h1>Study access</h1>
        <label htmlFor="code">Access code</label>
        <input
          id="code" type="text" autoComplete="off" autoFocus
          value={code} onChange={(e) => setCode(e.target.value)}
          placeholder="e.g. R01-…"
        />
        {err && <div className="fe-form-error">{err}</div>}
        <button type="submit" disabled={busy || !code.trim()}>{busy ? 'Checking…' : 'Continue'}</button>
        <div className="fe-contact">
          Problem with your code? Contact:{' '}
          {contact ? <a href={`mailto:${contact}`}>{contact}</a> : <em>(contact not configured)</em>}
        </div>
      </form>
    </div>
  )
}
