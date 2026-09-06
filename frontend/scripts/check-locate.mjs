// Does the quote matcher find the quotes the pipeline verified?
//
// The quotes were checked against GROBID's extraction; this view has to find them in
// pdf.js's, and the two never agree exactly. That gap is the risk in the whole split
// view, so it is measured here against the real documents in data/ rather than assumed.
// No network, no model, no cost.
//
//   node frontend/scripts/check-locate.mjs [submission_id]
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import * as pdfjsLib from 'pdfjs-dist/legacy/build/pdf.mjs'
import { pageTokens, findWindow, words } from '../src/pdf/locate.js'

const REPO = path.resolve(fileURLToPath(new URL('../..', import.meta.url)))
const DATA = path.join(REPO, 'data')
const STD_FONTS = path.join(REPO, 'frontend', 'node_modules', 'pdfjs-dist', 'standard_fonts') + path.sep

async function loadPages(pdfPath) {
  const data = new Uint8Array(fs.readFileSync(pdfPath))
  const doc = await pdfjsLib.getDocument({ data, isEvalSupported: false, standardFontDataUrl: STD_FONTS }).promise
  const pages = []
  for (let i = 1; i <= doc.numPages; i++) {
    const page = await doc.getPage(i)
    const tc = await page.getTextContent()
    pages.push({ tokens: pageTokens(tc) })
  }
  await doc.destroy()
  return pages
}

function best(pages, quote) {
  const qw = words(quote)
  if (qw.length < 4) return null
  let b = null
  pages.forEach((pg, i) => {
    const hit = findWindow(pg.tokens, qw)
    if (hit && (!b || hit.score > b.score)) b = { ...hit, page: i + 1 }
  })
  return b
}

const sid = process.argv[2] || 'transducing_language_models'
const sub = path.join(DATA, sid)

// 1. the submission's own claim quotes
const claims = JSON.parse(fs.readFileSync(path.join(sub, `${sid}_claims.json`), 'utf8'))
const pages = await loadPages(path.join(sub, `${sid}.pdf`))
console.log(`\n=== ${sid}: claim evidence quotes vs the submission PDF (${pages.length} pages) ===`)
let ok = 0, n = 0
for (const c of claims.claims || []) {
  const q = c.evidence_quote || ''
  if (!q.trim()) continue
  n++
  const b = best(pages, q)
  if (b) ok++
  console.log(`  ${b ? 'FOUND' : 'MISS '}  ${c.id}  ${b ? `p${b.page} score=${b.score.toFixed(2)}` : ''}  "${q.slice(0, 70).replace(/\s+/g, ' ')}…"`)
}
console.log(`  -> ${ok}/${n}`)

// 2. verified paper quotes from Artifact A against each prior paper's own PDF
const aPath = path.join(sub, `${sid}_artifact_a.json`)
if (fs.existsSync(aPath)) {
  const a = JSON.parse(fs.readFileSync(aPath, 'utf8'))
  const byPaper = new Map()
  for (const e of a.claims || []) {
    for (const c of e.comparisons || []) {
      const qs = []
      for (const p of c.evidence_pairs || []) {
        if (p.paper_quote_verified && p.paper_quote) qs.push(p.paper_quote)
      }
      for (const seg of c.paper_realization || []) {
        if (seg.kind === 'quote' && seg.verified && seg.content) qs.push(seg.content)
      }
      if (!qs.length) continue
      if (!byPaper.has(c.paper_id)) byPaper.set(c.paper_id, { title: c.title, quotes: [] })
      byPaper.get(c.paper_id).quotes.push(...qs)
    }
  }
  console.log(`\n=== prior-work quotes vs their own PDFs (${byPaper.size} papers) ===`)
  let pok = 0, pn = 0, missing = 0
  for (const [pid, info] of byPaper) {
    const pdf = path.join(sub, 'related_work_data', 'pdfs', `${pid}.pdf`)
    if (!fs.existsSync(pdf)) { missing++; continue }
    let pgs
    try { pgs = await loadPages(pdf) } catch (e) { console.log(`  [pdf error] ${info.title}: ${e.message}`); continue }
    let o = 0
    for (const q of info.quotes) {
      pn++
      if (best(pgs, q)) { o++; pok++ }
      else console.log(`      MISS: "${q.slice(0, 110).replace(/\s+/g, ' ')}…"`)
    }
    console.log(`  ${o}/${info.quotes.length}  ${info.title.slice(0, 62)}`)
  }
  console.log(`  -> ${pok}/${pn} quotes located; ${missing} papers had no PDF on disk`)
}
