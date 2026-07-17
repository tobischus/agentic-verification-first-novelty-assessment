import { useEffect, useState } from 'react'

// Only the two genuinely-long stages get a progress bar; the per-step list is gone.
const LONG_STAGES = new Set(['retrieval', 'fetch_pdfs'])

function fmtDur(s) {
  s = Math.max(0, Math.round(s || 0))
  const m = Math.floor(s / 60), sec = s % 60
  return m ? `${m}m ${String(sec).padStart(2, '0')}s` : `${sec}s`
}

export default function StatusBar({ state, stageLabels }) {
  // Local 1s clock so elapsed/ETA tick smoothly between the parent's 2.5s polls.
  const [now, setNow] = useState(() => Date.now() / 1000)
  useEffect(() => {
    const iv = setInterval(() => setNow(Date.now() / 1000), 1000)
    return () => clearInterval(iv)
  }, [])

  const status = state?.status || ''
  const curName = state?.current_stage?.name
  if (status === 'completed' || status === 'failed' || !curName || !LONG_STAGES.has(curName)) {
    return null
  }

  const p = state?.progress
  let phase = stageLabels?.[curName] || 'Working…'
  let determinate = false, pct = null, eta = null, done = 0, total = 0, elapsed = 0
  if (p && now - (p.updated_epoch || 0) < 120) {
    phase = p.phase || phase
    elapsed = Math.max(0, now - (p.started_epoch || now))
    determinate = !p.indeterminate && p.total > 0
    done = p.done; total = p.total
    if (determinate) {
      const frac = Math.min(1, p.done / p.total)
      pct = Math.round(frac * 100)
      if (p.done > 0 && frac < 1) {
        const rate = p.done / elapsed
        if (rate > 0) eta = (p.total - p.done) / rate
      }
    }
  }

  return (
    <div className="panel progress">
      <div className="progress-label">
        <span>{phase}</span>
        {determinate && <span>{done}/{total}</span>}
      </div>
      <div className="progress-track">
        <div
          className={'progress-fill' + (determinate ? '' : ' indeterminate')}
          style={determinate ? { width: `${pct}%` } : undefined}
        />
      </div>
      <div className="progress-meta">
        <span>{determinate ? `${pct}%` : 'estimating…'}</span>
        {eta != null
          ? <span>≈ {fmtDur(eta)} remaining</span>
          : <span>{fmtDur(elapsed)} elapsed</span>}
      </div>
    </div>
  )
}
