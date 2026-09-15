// REST client for the study API. Same-origin in production (see backend/app.py);
// vite.config.js proxies /api during `npm run dev`.

let csrfToken = null

function getCookie(name) {
  const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'))
  return m ? decodeURIComponent(m[1]) : null
}

async function req(method, path, body) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const csrf = csrfToken || getCookie('fe_csrf')
  if (csrf && method !== 'GET') headers['x-fe-csrf'] = csrf
  const r = await fetch(path, {
    method,
    headers,
    credentials: 'same-origin',
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  let data = null
  const text = await r.text()
  try { data = text ? JSON.parse(text) : null } catch { data = text }
  if (!r.ok) {
    const err = new Error((data && (data.detail || data.error)) || r.statusText || 'request failed')
    err.status = r.status
    err.data = data
    throw err
  }
  return data
}

export const api = {
  assetUrl: (id) => `/api/assets/${encodeURIComponent(id)}`,

  async login(code) {
    const d = await req('POST', '/api/auth/login', { code })
    csrfToken = d.csrf
    return d
  },
  logout: () => req('POST', '/api/auth/logout', {}),
  me: () => req('GET', '/api/me'),
  consent: (body) => req('POST', '/api/consent', body),

  listTasks: () => req('GET', '/api/tasks'),
  getTask: (assignmentId) => req('GET', `/api/tasks/${assignmentId}`),
  setFamiliarity: (body) => req('POST', '/api/familiarity', body),
  saveDraft: (assignmentId, body) => req('POST', `/api/tasks/${assignmentId}/draft`, body),
  submitTask: (assignmentId, body) => req('POST', `/api/tasks/${assignmentId}/submit`, body),
  reportIssue: (body) => req('POST', '/api/issues', body),
  exportMine: () => req('GET', '/api/export/mine'),

  admin: {
    overview: () => req('GET', '/api/admin/overview'),
    technicalIssues: () => req('GET', '/api/admin/technical-issues'),
    resolveIssue: (issueId) => req('POST', '/api/admin/technical-issues/resolve', { issue_id: issueId }),
    resetCode: (participantId) => req('POST', '/api/admin/participants/reset-code', { participant_id: participantId }),
    lock: (participantId, locked) => req('POST', '/api/admin/participants/lock', { participant_id: participantId, locked }),
    closeStudy: (confirm) => req('POST', '/api/admin/study/close', { confirm }),
    exportUrl: () => '/api/admin/export',
  },
}

export function setCsrfToken(t) { csrfToken = t }
export function idempotencyKey() {
  return 'idem-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10)
}
