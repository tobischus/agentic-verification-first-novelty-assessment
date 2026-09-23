import { useEffect, useState } from 'react'
import { api } from '../api.js'

const STATUS_LABEL = { not_started: 'Not started', in_progress: 'In progress', submitted: 'Submitted' }

export default function TaskList({ me, onOpenTask, onReadPaper, onLogout, onError }) {
  const [tasks, setTasks] = useState(null)
  const [readingRequired, setReadingRequired] = useState(false)

  const load = () => api.listTasks().then((d) => { setTasks(d.tasks); setReadingRequired(!!d.reading_required) })
    .catch((e) => onError(String(e.message || e)))
  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (!tasks) return <div className="fe-page">Loading tasks…</div>

  const byPaper = {}
  for (const t of tasks) {
    const g = (byPaper[t.paper_id] ||= { title: t.paper_title, tasks: [], read: true })
    g.tasks.push(t)
    if (!t.paper_read_confirmed) g.read = false
  }

  const submitted = tasks.filter((t) => t.status === 'submitted').length

  return (
    <div className="fe-page">
      <div className="fe-topbar">
        <div>Signed in as <strong>{me.code_display}</strong></div>
        <div className="fe-topbar-actions">
          <button className="link" onClick={async () => {
            const mine = await api.exportMine()
            const blob = new Blob([JSON.stringify(mine, null, 1)], { type: 'application/json' })
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a'); a.href = url; a.download = 'my_responses.json'
            document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url)
          }}>Download my responses</button>
          <button className="link" onClick={onLogout}>Log out</button>
        </div>
      </div>

      <div className="fe-card">
        <h1>Your tasks</h1>
        <p className="muted">{submitted} of {tasks.length} submitted.</p>

        {Object.entries(byPaper).map(([paperId, group]) => {
          // Non-pilot study: the paper's tasks stay locked until its submission has been
          // read and confirmed (PaperRead.jsx; enforced by the server as well).
          const locked = readingRequired && !group.read
          return (
            <div key={paperId} className="fe-paper-group">
              <h2>{group.title}</h2>
              <div className="fe-task-rows">
                {readingRequired && (
                  <div className={'fe-read-row' + (group.read ? ' done' : '')}>
                    <span className={'fe-status ' + (group.read ? 'fe-status-submitted' : 'fe-status-not_started')}>
                      {group.read ? 'Read' : 'First'}
                    </span>
                    <span className="fe-task-label">Read the submission</span>
                    <button className={group.read ? 'secondary' : undefined} onClick={() => onReadPaper(paperId)}>
                      {group.read ? 'Open again' : 'Read the submission'}
                    </button>
                  </div>
                )}
                {group.tasks.sort((a, b) => a.order_index - b.order_index).map((t) => (
                  <div key={t.assignment_id} className={'fe-task-row' + (locked ? ' locked' : '')}>
                    <span className={'fe-status fe-status-' + t.status}>{STATUS_LABEL[t.status]}</span>
                    <span className="fe-task-label">
                      Comparison task{locked && <span className="muted"> — opens after you read the submission</span>}
                    </span>
                    <button disabled={locked} onClick={() => onOpenTask(t.assignment_id)}>
                      {locked ? 'Locked' : t.status === 'not_started' ? 'Start' : t.status === 'submitted' ? 'Review' : 'Resume'}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
