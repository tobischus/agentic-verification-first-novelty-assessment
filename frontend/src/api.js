// REST client for the novelty-assessment backend (FastAPI).
const BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8099'

async function j(method, path, body, timeoutMs = 30000) {
  const opts = { method, headers: {}, signal: AbortSignal.timeout(timeoutMs) }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const r = await fetch(BASE + path, opts)
  if (!r.ok) throw new Error((await r.text()) || r.statusText)
  return r.json()
}

export const api = {
  base: BASE,

  async upload(file, submissionId) {
    const fd = new FormData()
    fd.append('file', file)
    const url = submissionId
      ? `${BASE}/submissions?submission_id=${encodeURIComponent(submissionId)}`
      : `${BASE}/submissions`
    const r = await fetch(url, { method: 'POST', body: fd })
    if (!r.ok) throw new Error((await r.text()) || r.statusText)
    return r.json()
  },

  state: (id) => j('GET', `/submissions/${id}/state`),
  claims: (id) => j('GET', `/submissions/${id}/claims`),
  editClaims: (id, operations) => j('PATCH', `/submissions/${id}/claims`, { operations }),
  // HITL: reviewer sets/corrects the publication date (= retrieval cutoff)
  setDate: (id, publicationDate) => j('PATCH', `/submissions/${id}/date`, { publication_date: publicationDate }),
  papers: (id) => j('GET', `/submissions/${id}/papers`),
  editPapers: (id, edit) => j('PATCH', `/submissions/${id}/papers`, edit),

  async uploadPaperPdf(id, paperId, file) {
    const fd = new FormData()
    fd.append('file', file)
    const r = await fetch(`${BASE}/submissions/${id}/papers/${paperId}/pdf`, { method: 'POST', body: fd })
    if (!r.ok) throw new Error((await r.text()) || r.statusText)
    return r.json()
  },

  async addPaper(id, { query, file } = {}) {
    const fd = new FormData()
    if (query) fd.append('query', query)
    if (file) fd.append('file', file)
    const r = await fetch(`${BASE}/submissions/${id}/papers/add`, { method: 'POST', body: fd })
    if (!r.ok) throw new Error((await r.text()) || r.statusText)
    return r.json()
  },
  approve: (id, cp) => j('POST', `/submissions/${id}/checkpoints/${cp}/approve`),
  artifact: (id, name) => j('GET', `/submissions/${id}/${name}`),
  fulltextStatus: (id) => j('GET', `/submissions/${id}/review/fulltext-status`),
  reviewClaims: (id) => j('GET', `/submissions/${id}/review/claims`),
  // starts the agent in the background (non-blocking); returns {status: running|done, review?}
  computeClaim: (id, claimId) => j('POST', `/submissions/${id}/review/claim/${claimId}`),
  // live progress of the running agent: {status, step, max_steps, trajectory[], cost, review?}
  claimLive: (id, claimId) => j('GET', `/submissions/${id}/review/claim/${claimId}/live`, undefined, 8000),
  agentCost: (id) => j('GET', `/submissions/${id}/agent-cost`),
  // aggregate token/cost across the whole run (document processing, claims,
  // retrieval, review) -- shown as the same cost badge on every tab
  pipelineCost: (id) => j('GET', `/submissions/${id}/pipeline-cost`),
  // cross-claim summary: overlapping prior work per claim (no verdict)
  reviewSummary: (id) => j('GET', `/submissions/${id}/review/summary`),
  // overall novelty conclusion (LLM-synthesised from the gathered evidence)
  reviewConclusion: (id) => j('GET', `/submissions/${id}/review/conclusion`),
  generateConclusion: (id) => j('POST', `/submissions/${id}/review/conclusion`),

  async report(id) {
    const r = await fetch(`${BASE}/submissions/${id}/report`)
    if (!r.ok) throw new Error((await r.text()) || r.statusText)
    return r.text()
  },

  // The finished assessment as plain text -- the exact artifact used in the system
  // comparison. Rendered from Artifact A + B by a template, so it is stable across calls.
  async reviewExport(id) {
    const r = await fetch(`${BASE}/submissions/${id}/review/export`)
    if (!r.ok) throw new Error((await r.text()) || r.statusText)
    return r.text()
  },
}
