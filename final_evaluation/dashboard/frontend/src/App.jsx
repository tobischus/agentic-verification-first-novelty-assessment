import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import { clearAllForParticipant } from './outbox.js'
import Login from './pages/Login.jsx'
import Instructions from './pages/Instructions.jsx'
import TaskList from './pages/TaskList.jsx'
import TaskRate from './pages/TaskRate.jsx'
import Done from './pages/Done.jsx'
import Admin from './pages/Admin.jsx'

// Deliberately no router library: five screens, a linear flow, and the extra dependency
// would not buy readability at this size. `view` is the single source of truth for
// which screen shows; browser Back is handled by pushing state for each transition
// (see go()) so it moves between screens instead of losing in-progress work.

const PILOT_BANNER = 'Development pilot — excluded from final study.'

export default function App() {
  const [me, setMe] = useState(undefined) // undefined = loading, null = logged out
  const [view, setView] = useState('login') // login | instructions | tasks | rate | done | admin
  const [activeAssignmentId, setActiveAssignmentId] = useState(null)
  const [err, setErr] = useState('')

  const refreshMe = useCallback(async () => {
    try {
      const d = await api.me()
      setMe(d)
      return d
    } catch {
      setMe(null)
      return null
    }
  }, [])

  useEffect(() => {
    refreshMe().then((d) => {
      if (d) setView(d.role === 'admin' ? 'admin' : d.consented ? 'tasks' : 'instructions')
      else setView('login')
    })
  }, [refreshMe])

  const go = useCallback((next, extra = {}) => {
    setView(next)
    if (extra.assignmentId !== undefined) setActiveAssignmentId(extra.assignmentId)
    window.history.pushState({ view: next, assignmentId: extra.assignmentId ?? null }, '')
  }, [])

  useEffect(() => {
    const onPop = (e) => {
      const s = e.state
      if (s) { setView(s.view); setActiveAssignmentId(s.assignmentId ?? null) }
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const onLoggedIn = async () => {
    const d = await refreshMe()
    go(d.role === 'admin' ? 'admin' : d.consented ? 'tasks' : 'instructions')
  }

  const onLogout = async () => {
    const pid = me?.participant_id
    try { await api.logout() } catch { /* proceed to clear local state regardless */ }
    if (pid) await clearAllForParticipant(pid)
    setMe(null)
    go('login')
  }

  if (me === undefined) return <div className="fe-loading">Loading…</div>

  return (
    <div className="fe-app">
      <div className="fe-pilot-banner">{PILOT_BANNER}</div>
      {err && <div className="fe-error-bar">{err} <button className="link" onClick={() => setErr('')}>dismiss</button></div>}
      {view === 'login' && <Login onLoggedIn={onLoggedIn} />}
      {view === 'instructions' && me && (
        <Instructions me={me} onConsented={() => { refreshMe(); go('tasks') }} onLogout={onLogout} />
      )}
      {view === 'tasks' && me && (
        <TaskList
          me={me}
          onOpenTask={(id) => go('rate', { assignmentId: id })}
          onLogout={onLogout}
          onError={setErr}
        />
      )}
      {view === 'rate' && me && activeAssignmentId && (
        <TaskRate
          me={me}
          assignmentId={activeAssignmentId}
          onDone={() => go('done')}
          onBack={() => go('tasks')}
          onError={setErr}
        />
      )}
      {view === 'done' && me && <Done me={me} onBack={() => go('tasks')} onLogout={onLogout} />}
      {view === 'admin' && me && me.role === 'admin' && <Admin me={me} onLogout={onLogout} />}
    </div>
  )
}
