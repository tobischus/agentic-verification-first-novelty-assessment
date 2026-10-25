// REST client for the backend API.
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
  pdfUrl: (id) => `${BASE}/submissions/${encodeURIComponent(id)}/pdf`,
  paperPdfUrl: (id, paperId) =>
    `${BASE}/submissions/${encodeURIComponent(id)}/papers/${encodeURIComponent(paperId)}/pdf`,

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
  reviewClaims: (id) => j('GET', `/submissions/${id}/review/claims`),
  computeClaim: (id, claimId) => j('POST', `/submissions/${id}/review/claim/${claimId}`),
  claimLive: (id, claimId) => j('GET', `/submissions/${id}/review/claim/${claimId}/live`, undefined, 8000),
  ensureClaimAssessment: (id, claimId) =>
    j('POST', `/submissions/${id}/review/claim/${claimId}/assessment`, undefined, 120000),
  finalizeReview: (id) => j('POST', `/submissions/${id}/review/finalize`, undefined, 300000),

  async reviewExport(id) {
    const r = await fetch(`${BASE}/submissions/${id}/review/export`)
    if (!r.ok) throw new Error((await r.text()) || r.statusText)
    return r.text()
  },

  quoteIndex: (id) => j('GET', `/submissions/${id}/review/quote_index`),
}
