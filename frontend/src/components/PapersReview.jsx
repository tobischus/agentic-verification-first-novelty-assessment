import { useEffect, useState } from 'react'
import { api } from '../api'
import PipelineCostBadge from './PipelineCostBadge.jsx'

// Map long Semantic Scholar venue names to short, readable abbreviations.
const VENUE_ABBR = [
  [/empirical methods in natural language processing/i, 'EMNLP'],
  [/north american chapter/i, 'NAACL'],
  [/association for computational linguistics/i, 'ACL'],
  [/neural information processing systems|neurips|\bnips\b/i, 'NeurIPS'],
  [/learning representations/i, 'ICLR'],
  [/international conference on machine learning/i, 'ICML'],
  [/computer vision and pattern recognition/i, 'CVPR'],
  [/international conference on computer vision/i, 'ICCV'],
  [/european conference on computer vision/i, 'ECCV'],
  [/knowledge discovery and data mining/i, 'KDD'],
  [/web search and data mining/i, 'WSDM'],
  [/world wide web|the web conference/i, 'WWW'],
  [/information and knowledge management/i, 'CIKM'],
  [/research and development in information retrieval|\bsigir\b/i, 'SIGIR'],
  [/aaai conference on artificial intelligence/i, 'AAAI'],
  [/international joint conference on artificial intelligence/i, 'IJCAI'],
  [/international conference on computational linguistics/i, 'COLING'],
  [/transactions of the association for computational linguistics/i, 'TACL'],
  [/arxiv/i, 'arXiv'],
]
function abbrevVenue(v) {
  if (!v) return ''
  for (const [re, ab] of VENUE_ABBR) if (re.test(v)) return ab
  return v.length > 24 ? v.slice(0, 22) + '…' : v
}
function fmtAuthors(a) {
  if (!a) return ''
  const list = a.split(/,\s*/).filter(Boolean)
  if (!list.length) return ''
  const first = list[0].trim().split(/\s+/).slice(-1)[0]
  return list.length > 1 ? `${first} et al.` : list[0]
}
const s2Url = (id) => (/^[0-9a-f]{40}$/i.test(id || '') ? `https://www.semanticscholar.org/paper/${id}` : null)

// Checkpoint 2: validate the related-work pool (grouped into topical clusters); add missing papers.
export default function PapersReview({ submissionId, status, onApproved }) {
  const [papers, setPapers] = useState(null)
  const [remove, setRemove] = useState(new Set())
  const [open, setOpen] = useState(new Set())
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [addOpen, setAddOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [adding, setAdding] = useState(false)
  const [addErr, setAddErr] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const [pdfBusy, setPdfBusy] = useState(new Set())   // paper_ids currently uploading a PDF
  const [pdfErr, setPdfErr] = useState({})            // paper_id -> error message

  // This component mounts as soon as retrieval is done (tab becomes available) --
  // which is BEFORE the fetch_pdfs stage has finished downloading the PDFs. A single
  // mount-time fetch would therefore snapshot a half-downloaded pool (only the first
  // PDF present -> everything else shows "no PDF" forever). Re-fetch on every pipeline
  // status transition so that when the 'papers' checkpoint is reached (all PDFs on
  // disk) the pdf_available flags refresh to their true values.
  useEffect(() => {
    api.papers(submissionId).then((d) => setPapers(d.papers)).catch((e) => setErr(String(e)))
  }, [submissionId, status])

  const uploadPdf = async (paperId, file) => {
    if (!file) return
    setPdfBusy((s) => new Set(s).add(paperId))
    setPdfErr((e) => ({ ...e, [paperId]: '' }))
    try {
      await api.uploadPaperPdf(submissionId, paperId, file)
      setPapers((ps) => ps.map((p) => (p.paper_id === paperId ? { ...p, pdf_available: true } : p)))
    } catch (e) {
      setPdfErr((er) => ({ ...er, [paperId]: String(e) }))
    } finally {
      setPdfBusy((s) => { const n = new Set(s); n.delete(paperId); return n })
    }
  }

  const toggle = (id, setFn) =>
    setFn((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n })

  const doAdd = async (payload) => {
    setAdding(true); setAddErr('')
    try {
      const r = await api.addPaper(submissionId, payload)
      if (r.papers) setPapers(r.papers)
      if (!r.added) setAddErr(r.reason || 'Could not add the paper.')
      else setQuery('')
    } catch (e) {
      setAddErr(String(e))
    } finally {
      setAdding(false)
    }
  }

  const approve = async () => {
    setBusy(true); setErr('')
    try {
      if (remove.size) await api.editPapers(submissionId, { remove: [...remove] })
      await api.approve(submissionId, 'papers')
      onApproved()
    } catch (e) {
      setErr(String(e)); setBusy(false)
    }
  }

  if (err && !papers) return <div className="error">{err}</div>
  if (!papers) return <div className="panel">Loading related work…</div>

  const renderCard = (p) => {
    const removed = remove.has(p.paper_id)
    const pct = p.relevance != null ? Math.round(Math.max(0, Math.min(1, p.relevance)) * 100) : null
    const relCls = pct == null ? '' : pct >= 80 ? 'high' : pct >= 60 ? 'mid' : 'low'
    const url = s2Url(p.paper_id)
    const meta = [fmtAuthors(p.authors), p.year, abbrevVenue(p.venue)].filter(Boolean).join(' · ')
    return (
      <li key={p.paper_id} className={'pcard' + (removed ? ' removed' : '')}>
        <input className="pkeep" type="checkbox" checked={!removed}
          onChange={() => toggle(p.paper_id, setRemove)} />
        <div className="pbody">
          <div className="ptitle-row">
            <span className="ptitle">{p.title}</span>
            {p.cited_paper && <span className="badge">cited</span>}
            {p.added_by && <span className="badge added">added</span>}
            {p.pdf_available
              ? <span className="pdfbadge ok" title="A PDF was downloaded for this paper">PDF ✓</span>
              : <span className="pdfbadge warn" title="No PDF could be downloaded automatically">⚠ no PDF</span>}
            {url && <a className="pext" href={url} target="_blank" rel="noreferrer" title="Open in Semantic Scholar">↗</a>}
          </div>
          {meta && <div className="pmeta muted">{meta}</div>}
          {!p.pdf_available && (
            <div className="pdf-upload">
              <label className="link pdf-upload-btn">
                {pdfBusy.has(p.paper_id) ? 'Uploading…' : '⬆ upload PDF for this paper'}
                <input type="file" accept="application/pdf" hidden disabled={pdfBusy.has(p.paper_id)}
                  onChange={(e) => uploadPdf(p.paper_id, e.target.files[0])} />
              </label>
              {pdfErr[p.paper_id] && <span className="pdf-upload-err">{pdfErr[p.paper_id]}</span>}
            </div>
          )}
          {pct != null && (
            <div className="prel">
              <span className="prel-label">Relevance</span>
              <span className="prel-track"><span className={'prel-fill ' + relCls} style={{ width: pct + '%' }} /></span>
              <span className="prel-val">{pct}%</span>
            </div>
          )}
          {p.abstract && (
            <button className="link abs-toggle" onClick={() => toggle(p.paper_id, setOpen)}>
              {open.has(p.paper_id) ? 'hide abstract' : 'abstract'}
            </button>
          )}
          {open.has(p.paper_id) && <p className="abstract">{p.abstract}</p>}
        </div>
      </li>
    )
  }

  // Group the final related work by topical cluster (reviewer-added papers last).
  const groups = {}
  papers.forEach((p) => {
    const key = p.added_by ? '_added'
      : (p.cluster != null && p.cluster >= 0 ? `c${p.cluster}` : '_none')
    if (!groups[key]) {
      groups[key] = {
        label: key === '_added' ? 'Added by reviewer'
          : (p.cluster_label || (key === '_none' ? 'Related work' : `Cluster ${p.cluster + 1}`)),
        papers: [], best: 0,
      }
    }
    groups[key].papers.push(p)
    groups[key].best = Math.max(groups[key].best, p.relevance || 0)
  })
  const order = Object.keys(groups).sort((a, b) => {
    if (a === '_added') return 1
    if (b === '_added') return -1
    return groups[b].best - groups[a].best
  })
  const multiCluster = order.filter((k) => k !== '_added').length > 1

  const nNoPdf = papers.filter((p) => !p.pdf_available).length

  return (
    <div className="panel checkpoint">
      <div className="paper-head-row">
        <h2>Related work — {papers.length - remove.size}/{papers.length} kept</h2>
        <PipelineCostBadge submissionId={submissionId} />
      </div>
      <p className="muted">Uncheck papers that are not relevant; add any missing ones below.</p>
      {nNoPdf > 0 && (
        <p className="muted pdf-summary">
          <strong>{nNoPdf}</strong> paper{nNoPdf === 1 ? '' : 's'} without a downloadable PDF —
          upload one manually where you see the ⚠ badge below (needed only if that paper ends up in a deep dive during Review).
        </p>
      )}

      {/* collapsible add box */}
      <div className="addbox">
        <button className="addbox-head" onClick={() => setAddOpen((o) => !o)}>
          <span>＋ Add related paper</span>
          <span className="chev">{addOpen ? '▾' : '▸'}</span>
        </button>
        {addOpen && (
          <div className="addbox-body">
            <div
              className={'dropzone' + (dragOver ? ' over' : '')}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setDragOver(false); doAdd({ file: e.dataTransfer.files?.[0] }) }}
              onClick={() => document.getElementById('add-pdf').click()}
              role="button"
            >
              <input id="add-pdf" type="file" accept="application/pdf" hidden
                onChange={(e) => doAdd({ file: e.target.files[0] })} />
              <span>Drag &amp; drop a PDF, or <span className="browse">browse</span></span>
            </div>
            <div className="addrow">
              <input
                type="text" placeholder="…or paste a DOI / arXiv id / paper title"
                value={query} onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && query.trim() && doAdd({ query: query.trim() })}
              />
              <button className="secondary" disabled={adding || !query.trim()} onClick={() => doAdd({ query: query.trim() })}>
                {adding ? 'Adding…' : 'Add'}
              </button>
            </div>
            {adding && <div className="muted">Resolving paper…</div>}
            {addErr && <div className="error">{addErr}</div>}
          </div>
        )}
      </div>

      {order.map((key) => (
        <div key={key} className="cluster">
          {(multiCluster || key === '_added') && <h3 className="cluster-head">{groups[key].label}</h3>}
          <ul className="papers cards">
            {groups[key].papers.map(renderCard)}
          </ul>
        </div>
      ))}

      <div className="actions">
        <button disabled={busy} onClick={approve}>{busy ? 'Submitting…' : 'Approve & continue'}</button>
      </div>
      {err && <div className="error">{err}</div>}
    </div>
  )
}
