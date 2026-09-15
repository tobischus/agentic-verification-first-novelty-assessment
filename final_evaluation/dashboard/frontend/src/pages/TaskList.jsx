import { useEffect, useState } from 'react'
import { api } from '../api.js'

const STATUS_LABEL = { not_started: 'Not started', in_progress: 'In progress', submitted: 'Submitted' }

export default function TaskList({ me, onOpenTask, onLogout, onError }) {
  const [tasks, setTasks] = useState(null)

  const load = () => api.listTasks().then((d) => setTasks(d.tasks)).catch((e) => onError(String(e.message || e)))
  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (!tasks) return <div className="fe-page">Loading tasks…</div>

  const byPaper = {}
  for (const t of tasks) (byPaper[t.paper_id] ||= { title: t.paper_title, tasks: [] }).tasks.push(t)

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

        {Object.entries(byPaper).map(([paperId, group]) => (
          <div key={paperId} className="fe-paper-group">
            <h2>{group.title}</h2>
            <div className="fe-task-rows">
              {group.tasks.sort((a, b) => a.order_index - b.order_index).map((t) => (
                <div key={t.assignment_id} className="fe-task-row">
                  <span className={'fe-status fe-status-' + t.status}>{STATUS_LABEL[t.status]}</span>
                  <span className="fe-task-label">Comparison task</span>
                  <button onClick={() => onOpenTask(t.assignment_id)}>
                    {t.status === 'not_started' ? 'Start' : t.status === 'submitted' ? 'Review' : 'Resume'}
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
