export default function Done({ onBack, onLogout }) {
  return (
    <div className="fe-center">
      <div className="fe-card fe-done">
        <h1>Task submitted</h1>
        <p>Thank you. Your response has been recorded.</p>
        <p className="muted">No results or comparisons between systems are shown here.</p>
        <div className="fe-actions">
          <button onClick={onBack}>Back to task list</button>
          <button className="secondary" onClick={onLogout}>Log out</button>
        </div>
      </div>
    </div>
  )
}
