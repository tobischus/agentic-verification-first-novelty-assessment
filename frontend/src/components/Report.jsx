import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { api } from '../api'

export default function Report({ submissionId }) {
  const [md, setMd] = useState('')
  const [err, setErr] = useState('')

  useEffect(() => {
    api.report(submissionId).then(setMd).catch((e) => setErr(String(e)))
  }, [submissionId])

  if (err) return <div className="error">{err}</div>
  if (!md) return <div className="panel">Loading report…</div>
  return (
    <div className="panel report">
      <ReactMarkdown>{md}</ReactMarkdown>
    </div>
  )
}
