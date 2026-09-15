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
// never looks a prior-work quote up as something to jump to. Those quotes still render
// as verified (✓) blockquotes -- they are already fully shown in the report text, which
// is what PROTOCOL.md means by "im Report navigierbar" -- they simply are not clickable.

const norm = (s) => (s || '').replace(/\s+/g, ' ').trim()
const unquote = (s) => norm(s).replace(/^[“"]/, '').replace(/[”"]$/, '')

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

function Quote({ text, target, activeId, onPick }) {
  const clickable = !!target
  const active = clickable && activeId === target.id
  return (
    <blockquote
      className={'rz-quote' + (clickable ? ' qjump' : '') + (active ? ' active' : '')}
      onClick={clickable ? () => onPick(target) : undefined}
      title={clickable ? 'Show this passage in the PDF' : undefined}
    >
      <span className="rz-qmark" title="Verified verbatim in its source">✓</span>
      <span className="rz-qtext">{text}</span>
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

export function renderReportMarkdown(text, quoteIndex, activeId, onPick) {
  const lines = (text || '').split('\n')
  const subMap = new Map((quoteIndex?.submission || []).map((q) => [q.text, q.id]))
  // `quoteIndex.papers` (cited prior-work quotes) is intentionally NEVER consulted here
  // -- see the file header. Only a submission-side quote resolves to a click target.
  const resolve = (quoteText) => (subMap.has(quoteText) ? { id: subMap.get(quoteText) } : null)

  const out = []
  let i = 0, key = 0
  while (i < lines.length) {
    const line = lines[i]
    const t = line.trim()
    if (!t) { i++; continue }

    if (t === '---') { out.push(<hr key={key++} className="rr-hr" />); i++; continue }

    const heading = t.match(/^(#{1,5})\s+(.*)$/)
    if (heading) {
      const level = heading[1].length
      const Tag = `h${Math.min(level + 1, 6)}`
      out.push(<Tag key={key++} className={'rr-h rr-h' + level}>{inline(heading[2], `h${key}`)}</Tag>)
      i++; continue
    }

    if (t.startsWith('|')) {
      const rows = []
      while (i < lines.length && lines[i].trim().startsWith('|')) { rows.push(lines[i].trim()); i++ }
      out.push(<Table key={key++} rows={rows} keyPrefix={`t${key}`} />)
      continue
    }

    if (t.startsWith('> ')) {
      const quoteText = unquote(t.slice(2))
      const target = resolve(quoteText)
      out.push(<Quote key={key++} text={quoteText} target={target} activeId={activeId} onPick={onPick} />)
      i++; continue
    }

    if (/^-\s/.test(t)) {
      const items = []
      while (i < lines.length && /^\s*-\s/.test(lines[i])) {
        const nested = /^\s\s/.test(lines[i])
        items.push({ nested, text: lines[i].trim().replace(/^-\s/, '') })
        i++
      }
      out.push(
        <ul key={key++} className="rr-list">
          {items.map((it, ii) => (
            <li key={ii} className={it.nested ? 'rr-nested' : undefined}>{inline(it.text, `l${key}-${ii}`)}</li>
          ))}
        </ul>,
      )
      continue
    }

    out.push(<p key={key++} className="rr-p">{inline(t, `p${key}`)}</p>)
    i++
  }
  return out
}

export default function ReportRenderer({ text, quoteIndex, activeId, onPick }) {
  return <div className="rr-doc">{renderReportMarkdown(text, quoteIndex, activeId, onPick)}</div>
}
