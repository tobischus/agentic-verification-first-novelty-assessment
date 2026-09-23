import { useState } from 'react'
import { api } from '../api.js'

// No system names, no study framing beyond the code field itself -- PROTOCOL.md section
// 8 ("Keine Systemnamen auf der Loginseite"). No contact line either: the raters are
// recruited personally and reach the study author directly (study author's decision,
// 2026-09-23).
export default function Login({ onLoggedIn }) {
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

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
      </form>
    </div>
  )
}
