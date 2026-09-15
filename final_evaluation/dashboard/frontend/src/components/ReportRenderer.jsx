// Renders one system's frozen markdown report, structurally the same way
// frontend/src/components/ReviewSummary.jsx renders the live pipeline's export text:
// headings/tables/blockquotes parsed from the text (never re-typed). This file does not
// import that component (it lives in a different, independent Vite app -- see
// vendor/pdf/README.md for why the PDF viewer itself is copied rather than imported);
// it mirrors the same parsing approach for the same reason: the report is a frozen
// document text, not a live API response.
//
// `quoteIndex` (agent/linear only) is {submission:[{id,text}],
// papers:{paper_id:{title,quotes:[{id,text}]}}, refs:{paper_id:"R#"}} -- see
// battle_export.quote_index()'s docstring. ONLY `submission` entries become click
// targets here, on purpose: `papers` indexes quotes from the CITED PRIOR-WORK papers
// (e.g. "R7 Zhou et al."), and PROTOCOL.md section 5 is explicit that a prior-work PDF
// is never served during E2, from any control, "auch nicht über PDF-Buttons". No such
// asset even exists in this study's database (import_pilot.py never imports one) --
// this is the second, UI-logic layer of that same boundary: even the id resolution
// never looks a prior-work quote up as something to jump to. Those quotes are still
// shown in full (that is what PROTOCOL.md means by "im Report navigierbar") and still
// carry the ✓ if the index says they were verified -- they simply are not clickable.
//
// TWO DIFFERENT THINGS, TWO DIFFERENT MARKS (they were conflated before):
//   ✓   a stored verbatim check MATCHED this quote in its source document. Shown only
//       when the quote's text is present in the quote index -- which battle_export's
//       quote_index() fills exclusively with verified spans. A quote the export itself
//       labelled "Not confirmed verbatim", and every quote in a report that ships no
//       index at all (deepreviewer, afzal, opennovelty), gets NO tick: an unknown check
//       status must not look like a passed one.
//   ⤴   this passage can be located in the submission PDF. A navigation affordance,
//       not a verification claim.

const norm = (s) => (s || '').replace(/\s+/g, ' ').trim()
const unquote = (s) => norm(s).replace(/^[“"]/, '').replace(/[”"]$/, '')

// The exact line battle_export._span() prints above a span it could NOT confirm.
const UNVERIFIED_MARKER = /^not confirmed verbatim:?$/i

function inline(text, keyPrefix) {
  const out = []
  const re = /\*\*(.+?)\*\*|\[([^\]]+)\]\(<?([^()>]+)>?\)/g
  let last = 0, m, i = 0
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index))
    if (m[1] !== undefined) {
      out.push(<strong key={`${keyPrefix}-b${i++}`}>{m[1]}</strong>)
    } else {
      out.push(<a key={`${keyPrefix}-a${i++}`} href={m[3]} target="_blank" rel="noreferrer">{m[2]}</a>)
    }
    last = re.lastIndex
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

function Quote({ text, verified, target, activeId, onPick }) {
  const clickable = !!target
  const active = clickable && activeId === target.id
  return (
    <blockquote
      className={'rz-quote' + (clickable ? ' qjump' : '') + (active ? ' active' : '')
                + (verified ? ' verified' : ' unverified')}
      onClick={clickable ? () => onPick(target) : undefined}
    >
      {verified ? (
        <span className="rz-qmark" title="A stored verbatim check matched this quote in its source document">✓</span>
      ) : (
        <span className="rz-qmark rz-qmark-none"
             title="No stored verbatim check for this quote (not confirmed, or this report carries no check)">–</span>
      )}
      <span className="rz-qtext">{text}</span>
      {clickable && (
        <button
          type="button"
          className="rz-qjump"
          title="Show this passage in the submission PDF"
          onClick={(e) => { e.stopPropagation(); onPick(target) }}
        >
          ⤴ PDF
        </button>
      )}
    </blockquote>
  )
}

function Table({ rows, keyPrefix }) {
  const cells = (line) => line.replace(/^\|/, '').replace(/\|$/, '').split('|')
    .map((c) => c.trim().replace(/&#124;/g, '|'))
  const head = cells(rows[0])
  const body = rows.slice(2).map(cells)
  return (
    <div className="rr-table-wrap">
      <table className="rr-table">
        <thead><tr>{head.map((h, i) => <th key={i}>{inline(h, `${keyPrefix}-h${i}`)}</th>)}</tr></thead>
        <tbody>
          {body.map((r, ri) => (
            <tr key={ri}>{r.map((c, ci) => <td key={ci}>{inline(c, `${keyPrefix}-${ri}-${ci}`)}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// A per-source-comparison heading in battle_export's layout: "### R11 — Title".
const DETAIL_HEADING = /^R\d+\s+[—-]\s+/

/** Parse the frozen report text into rendered items plus a table of contents.
 *
 *  Two passes on purpose: the first turns lines into items (headings stay identifiable
 *  as headings), the second groups each "### R# — ..." comparison and everything under
 *  it into a collapsed <details>. Grouping cannot be done in one pass without knowing
 *  where the next heading starts, and NOTHING is dropped in either pass -- a collapsed
 *  section still contains its full text, it is only folded.
 */
export function parseReport(text, quoteIndex, { idPrefix = 'r', activeId, onPick } = {}) {
  const lines = (text || '').split('\n')
  const subMap = new Map((quoteIndex?.submission || []).map((q) => [q.text, q.id]))
  const paperTexts = new Set(
    Object.values(quoteIndex?.papers || {}).flatMap((p) => (p.quotes || []).map((q) => q.text)),
  )
  const hasIndex = !!quoteIndex
  // `quoteIndex.papers` (cited prior-work quotes) is consulted ONLY to know whether a
  // quote passed its verbatim check -- never to build a click target. See file header.
  const resolve = (quoteText) => (subMap.has(quoteText) ? { id: subMap.get(quoteText) } : null)
  const isVerified = (quoteText) => hasIndex && (subMap.has(quoteText) || paperTexts.has(quoteText))

  const items = []
  const toc = []
  let i = 0, key = 0, headingNo = 0
  let prevNonEmpty = ''

  while (i < lines.length) {
    const line = lines[i]
    const t = line.trim()
    if (!t) { i++; continue }

    if (t === '---') {
      // battle_export prints "---" immediately before each "### R# — ..." section; that
      // rule is redundant once the section is its own collapsible block.
      const nextNonEmpty = lines.slice(i + 1).find((l) => l.trim())?.trim() || ''
      const nextIsDetail = /^#{2,4}\s+/.test(nextNonEmpty)
        && DETAIL_HEADING.test(nextNonEmpty.replace(/^#{2,4}\s+/, ''))
      if (!nextIsDetail) items.push({ type: 'node', node: <hr key={key++} className="rr-hr" /> })
      prevNonEmpty = t; i++; continue
    }

    const heading = t.match(/^(#{1,5})\s+(.*)$/)
    if (heading) {
      const level = heading[1].length
      const body = heading[2]
      const hid = `${idPrefix}-h${headingNo++}`
      const Tag = `h${Math.min(level + 1, 6)}`
      items.push({
        type: 'heading', level, text: body, id: hid,
        node: <Tag key={key++} id={hid} className={'rr-h rr-h' + level}>{inline(body, `h${key}`)}</Tag>,
      })
      if (level <= 2) toc.push({ id: hid, level, text: body })
      prevNonEmpty = t; i++; continue
    }

    if (t.startsWith('|')) {
      const rows = []
      while (i < lines.length && lines[i].trim().startsWith('|')) { rows.push(lines[i].trim()); i++ }
      items.push({ type: 'node', node: <Table key={key++} rows={rows} keyPrefix={`t${key}`} /> })
      prevNonEmpty = '|'; continue
    }

    if (t.startsWith('> ')) {
      const quoteText = unquote(t.slice(2))
      // The export's own "Not confirmed verbatim:" line wins over anything else: if it
      // says the check failed, no tick, whatever an index might contain.
      const declaredUnverified = UNVERIFIED_MARKER.test(prevNonEmpty.replace(/\*\*/g, '').trim())
      items.push({
        type: 'node',
        node: <Quote key={key++} text={quoteText} verified={!declaredUnverified && isVerified(quoteText)}
                    target={resolve(quoteText)} activeId={activeId} onPick={onPick} />,
      })
      prevNonEmpty = t; i++; continue
    }

    if (/^-\s/.test(t)) {
      const bullets = []
      while (i < lines.length && /^\s*-\s/.test(lines[i])) {
        const nested = /^\s\s/.test(lines[i])
        bullets.push({ nested, text: lines[i].trim().replace(/^-\s/, '') })
        i++
      }
      items.push({
        type: 'node',
        node: (
          <ul key={key++} className="rr-list">
            {bullets.map((it, ii) => (
              <li key={ii} className={it.nested ? 'rr-nested' : undefined}>{inline(it.text, `l${key}-${ii}`)}</li>
            ))}
          </ul>
        ),
      })
      prevNonEmpty = bullets[bullets.length - 1]?.text || ''
      continue
    }

    items.push({ type: 'node', node: <p key={key++} className="rr-p">{inline(t, `p${key}`)}</p> })
    prevNonEmpty = t; i++
  }

  // Second pass: fold each per-source comparison into a collapsed <details>.
  const nodes = []
  let j = 0
  while (j < items.length) {
    const it = items[j]
    if (it.type === 'heading' && it.level >= 3 && DETAIL_HEADING.test(it.text)) {
      const body = []
      let k = j + 1
      while (k < items.length && !(items[k].type === 'heading' && items[k].level <= it.level)) {
        body.push(items[k].node); k++
      }
      nodes.push(
        <details key={`d${j}`} className="rr-detail" id={it.id}>
          <summary className="rr-detail-summary">{it.text}</summary>
          <div className="rr-detail-body">{body}</div>
        </details>,
      )
      j = k
      continue
    }
    nodes.push(it.node)
    j++
  }
  return { nodes, toc }
}

export default function ReportRenderer({ text, quoteIndex, activeId, onPick, idPrefix = 'r',
                                        showToc = true }) {
  const { nodes, toc } = parseReport(text, quoteIndex, { idPrefix, activeId, onPick })
  const jump = (id) => {
    const el = document.getElementById(id)
    if (el) el.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }
  return (
    <div className="rr-doc">
      {showToc && toc.length > 1 && (
        <details className="rr-toc" open>
          <summary>Contents</summary>
          <ul>
            {toc.map((h) => (
              <li key={h.id} className={'rr-toc-l' + h.level}>
                <button type="button" className="link" onClick={() => jump(h.id)}>{h.text}</button>
              </li>
            ))}
          </ul>
        </details>
      )}
      <div className="rr-body">{nodes}</div>
    </div>
  )
}
