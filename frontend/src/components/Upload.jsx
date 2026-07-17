import { useState } from 'react'
import { api } from '../api'

export default function Upload({ onUploaded }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [dragOver, setDragOver] = useState(false)

  const start = async (f) => {
    if (!f) return
    if (!(f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'))) {
      setErr('Please choose a PDF file.'); return
    }
    if (f.size > 50 * 1024 * 1024) { setErr('PDF too large (max 50 MB).'); return }
    setBusy(true); setErr('')
    try {
      const r = await api.upload(f)
      onUploaded(r.submission_id)
    } catch (e) {
      setErr(String(e)); setBusy(false)
    }
  }

  const onDrop = (e) => { e.preventDefault(); setDragOver(false); start(e.dataTransfer.files?.[0]) }

  return (
    <div className="panel">
      <div className="step-label">STEP 1</div>
      <h2>Upload Research Paper</h2>
      <div
        className={'dropzone big' + (dragOver ? ' over' : '') + (busy ? ' busy' : '')}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => !busy && document.getElementById('pdf-input').click()}
        role="button"
      >
        <input
          id="pdf-input" type="file" accept="application/pdf" hidden
          onChange={(e) => start(e.target.files[0])}
        />
        <svg className="upload-icon" viewBox="0 0 24 24" width="34" height="34" fill="none"
             stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 16V4" /><path d="M7 9l5-5 5 5" /><path d="M5 20h14" />
        </svg>
        {busy ? (
          <div className="dz-main">Uploading…</div>
        ) : (
          <>
            <div className="dz-main">Drag &amp; drop a PDF, or <span className="browse">browse</span></div>
            <div className="dz-sub">Supports PDF up to 50 MB</div>
          </>
        )}
      </div>
      {err && <div className="error">{err}</div>}
    </div>
  )
}
