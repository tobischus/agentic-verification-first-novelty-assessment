import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Admin({ me, onLogout }) {
  const [overview, setOverview] = useState(null)
  const [err, setErr] = useState('')
  const [confirmClose, setConfirmClose] = useState('')
  const [resetResult, setResetResult] = useState(null)

  const load = () => {
    api.admin
      .overview()
      .then(setOverview)
      .catch((e) => setErr(String(e.message || e)))
  }
  useEffect(() => {
    load()
  }, [])

  if (!overview) return <div className="fe-page">{err || 'Loading admin overview…'}</div>

  return (
    <div className="fe-page">
      <div className="fe-topbar">
        <div>
          Admin — <strong>{overview.study?.title}</strong> ({overview.study?.status})
        </div>
        <button className="link" onClick={onLogout}>
          Log out
        </button>
      </div>

      {resetResult && (
        <div className="fe-card fe-reset-result">
          <strong>New code for {resetResult.code_display}:</strong>{' '}
          <code>{resetResult.new_code}</code>
          <p className="muted">Shown once. Copy it now and deliver it to the participant.</p>
          <button className="link" onClick={() => setResetResult(null)}>
            dismiss
          </button>
        </div>
      )}

      <div className="fe-card">
        <h2>Participants</h2>
        <table className="fe-admin-table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Consented</th>
              <th>Not started</th>
              <th>In progress</th>
              <th>Submitted</th>
              <th>Locked</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {overview.participants.map((p) => (
              <tr key={p.participant_id}>
                <td>
                  {p.code_display}
                  {p.is_test ? ' (test)' : ''}
                </td>
                <td>{p.consented ? 'yes' : 'no'}</td>
                <td>{p.counts.not_started || 0}</td>
                <td>{p.counts.in_progress || 0}</td>
                <td>{p.counts.submitted || 0}</td>
                <td>{p.locked ? 'yes' : 'no'}</td>
                <td>
                  <button
                    className="link"
                    onClick={async () => {
                      const r = await api.admin.resetCode(p.participant_id)
                      setResetResult(r)
                      load()
                    }}
                  >
                    reset code
                  </button>{' '}
                  <button
                    className="link"
                    onClick={async () => {
                      await api.admin.lock(p.participant_id, !p.locked)
                      load()
                    }}
                  >
                    {p.locked ? 'unlock' : 'lock'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="fe-card">
        <h2>Export</h2>
        <a className="fe-export-link" href={api.admin.exportUrl()}>
          Download full research export (.zip)
        </a>
        <p className="muted">
          ratings.jsonl, ratings_long.csv, assignments.csv, tasks.json, manifest.json, rubric.txt,
          protocol.md, completion.csv. Pseudonymised; no access codes or session secrets.
        </p>
      </div>

      <div className="fe-card">
        <h2>Close study</h2>
        <p className="muted">Stops accepting new responses. Cannot be undone from this screen.</p>
        <input
          type="text"
          placeholder={`type "${overview.study?.id}" to confirm`}
          value={confirmClose}
          onChange={(e) => setConfirmClose(e.target.value)}
        />
        <button
          className="danger"
          disabled={confirmClose !== overview.study?.id}
          onClick={async () => {
            await api.admin.closeStudy(confirmClose)
            load()
          }}
        >
          Close study
        </button>
      </div>
    </div>
  )
}
