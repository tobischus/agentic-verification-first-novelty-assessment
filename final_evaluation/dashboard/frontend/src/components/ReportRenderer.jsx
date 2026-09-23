// Renders one system's frozen markdown report, structurally the same way
// frontend/src/components/ReviewSummary.jsx renders the live pipeline's export text:
// headings/tables/blockquotes parsed from the text (never re-typed). This file does not
// import that component (it lives in a different, independent Vite app -- see
// vendor/pdf/README.md for why the PDF viewer itself is copied rather than imported);
// it mirrors the same parsing approach for the same reason: the report is a frozen
// document text, not a live API response. The rules both renderers share -- which phrase
// gets which colour, how "#cmp-2-R7" resolves -- live in ./assessmentStyle.js, which is
// byte-identical in both apps and checked by test_renderer_parity.py.
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

import {
  ASSESSMENT_LINE, CLAIM_HEADING, DETAIL_HEADING, OPEN_POINT_LINE, VERDICT_LINE, anchorId,
  assessment, claimOfPassages, groupReport, isGroupedLayout, jumpToId, resolveAnchor, subBlock,
} from './assessmentStyle.js'
import { colorFor } from '../vendor/pdf/PdfViewer.jsx'

// One colour per claim, the same as in the main app's Summary tab: the claim's text here
// and every submission passage filed under that claim in the PDF (TaskRate.jsx) share it.
export const claimColor = (n) => colorFor(n - 1)
// Alpha suffix for the passages that are not the one just jumped to.
export const DIM = '73'

const norm = (s) => (s || '').replace(/\s+/g, ' ').trim()
const unquote = (s) => norm(s).replace(/^[“"]/, '').replace(/[”"]$/, '')

// The exact line battle_export._span() prints above a span it could NOT confirm.
const UNVERIFIED_MARKER = /^not confirmed verbatim:?$/i

/** **bold**, [text](url) and the export's own "#cmp-<claim>-<ref>" jump links.
 *  A jump link is resolved against THIS panel's id prefix and scrolls in place; without a
 *  `ctx` it stays an ordinary anchor, so the parser is still usable outside a panel. */
function inline(text, keyPrefix, ctx) {
  const out = []
  const re = /\*\*(.+?)\*\*|\[([^\]]+)\]\(<?([^()>]+)>?\)/g
  let last = 0, m, i = 0
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index))
    if (m[1] !== undefined) {
      out.push(<strong key={`${keyPrefix}-b${i++}`}>{m[1]}</strong>)
    } else {
      const target = ctx ? resolveAnchor(ctx.idPrefix, m[3]) : null
      if (target) {
        out.push(
          <a key={`${keyPrefix}-j${i++}`} className="as-jump" href={`#${target}`}
             onClick={(e) => { e.preventDefault(); jumpToId(target) }}>{m[2]}</a>,
        )
      } else {
        // An external link is shown as its text only. The export links each source to its
        // arXiv PDF ("Source used: [v2 · 2023-07-18](https://arxiv.org/pdf/…)"), and a live
        // link would open the prior-work paper mid-rating -- PROTOCOL.md section 4 rules
        // that out "by button, link, direct URL". The version and date stay visible.
        out.push(<span key={`${keyPrefix}-a${i++}`} className="rr-extlink">{m[2]}</span>)
      }
    }
    last = re.lastIndex
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

function Quote({ text, verified, target, activeId, onPick, claim }) {
  const clickable = !!target
  const active = clickable && activeId === target.id
  return (
    <blockquote
      className={'rz-quote' + (clickable ? ' qjump' : '') + (active ? ' active' : '')
                + (verified ? ' verified' : ' unverified')}
      onClick={clickable ? () => onPick(target) : undefined}
    >
      {clickable && claim ? (
        <span className="qswatch" style={{ background: claimColor(claim) }}
              title={`Highlighted in this colour in the submission PDF (claim ${claim})`} />
      ) : null}
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

/** A table, with assessment cells coloured and any row carrying substantial-or-higher
 *  overlap marked. Only a cell that is ENTIRELY an assessment phrase is classified, so a
 *  title or a version date is never tinted by accident. */
function Table({ rows, keyPrefix, ctx }) {
  const cells = (line) => line.replace(/^\|/, '').replace(/\|$/, '').split('|')
    .map((c) => c.trim().replace(/&#124;/g, '|'))
  // A linked assessment reads "[partial overlap · material evidence](#cmp-2-R7)"; the
  // classification looks at the label, the link keeps working either way.
  const bare = (c) => c.replace(/^\[([^\]]+)\]\(#[^)]*\)$/, '$1')
  const head = cells(rows[0])
  const body = rows.slice(2).map(cells)
  return (
    <div className="rr-table-wrap">
      <table className="rr-table">
        <thead><tr>{head.map((h, i) => <th key={i}>{inline(h, `${keyPrefix}-h${i}`, ctx)}</th>)}</tr></thead>
        <tbody>
          {body.map((r, ri) => {
            const marks = r.map((c) => assessment(bare(c), { whole: true }))
            return (
              <tr key={ri} className={marks.some((a) => a && a.strong) ? 'as-cell-row' : undefined}>
                {r.map((c, ci) => (
                  <td key={ci} className={marks[ci] ? `as-cell ${marks[ci].className}` : undefined}>
                    {inline(c, `${keyPrefix}-${ri}-${ci}`, ctx)}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/** Parse the frozen report text into rendered items plus a table of contents.
 *
 *  Two passes on purpose: the first turns lines into items (headings stay identifiable
 *  as headings), the second groups each "### R# — ..." comparison and everything under
 *  it into a collapsed <details>, and the level-4 blocks inside it into their own boxes.
 *  Grouping cannot be done in one pass without knowing where the next heading starts, and
 *  NOTHING is dropped in either pass -- a collapsed section still contains its full text,
 *  it is only folded.
 */
export function parseReport(text, quoteIndex, { idPrefix = 'r', activeId, onPick } = {}) {
  const lines = (text || '').split('\n')
  const ctx = { idPrefix }
  const subMap = new Map((quoteIndex?.submission || []).map((q) => [q.text, q.id]))
  const paperTexts = new Set(
    Object.values(quoteIndex?.papers || {}).flatMap((p) => (p.quotes || []).map((q) => q.text)),
  )
  const hasIndex = !!quoteIndex
  // `quoteIndex.papers` (cited prior-work quotes) is consulted ONLY to know whether a
  // quote passed its verbatim check -- never to build a click target. See file header.
  const resolve = (quoteText) => (subMap.has(quoteText) ? { id: subMap.get(quoteText) } : null)
  const isVerified = (quoteText) => hasIndex && (subMap.has(quoteText) || paperTexts.has(quoteText))
  const claimOf = claimOfPassages(text, quoteIndex)

  const items = []
  const toc = []
  // v4 reports (battle_export reviewer-v4.0) are grouped by the shared rules in
  // assessmentStyle.js; anything older -- the pilot's frozen reports -- keeps exactly the
  // rendering it was rated in. Every branch below that is new is gated on this flag.
  const grouped = isGroupedLayout(text)
  let i = 0, key = 0, headingNo = 0
  let prevNonEmpty = ''
  let claimNo = 0
  let claimTextFor = 0

  while (i < lines.length) {
    const line = lines[i]
    const t = line.trim()
    if (!t) { i++; continue }

    if (t === '---' && grouped) {
      items.push({ type: 'node', hr: true, node: <hr key={key++} className="rr-hr" /> })
      prevNonEmpty = t; i++; continue
    }

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
      // The claim heading fixes which claim the "### R# — ..." sections below belong to;
      // together they are battle_export._anchor()'s two halves.
      const claim = CLAIM_HEADING.exec(body)
      if (claim) claimNo = Number(claim[1])
      // v4.4: the claim's own text, the next paragraph, links to its anchor in the PDF.
      claimTextFor = grouped && claim ? claimNo : 0
      const ref = DETAIL_HEADING.exec(body)
      items.push({
        type: 'heading', level, text: body, id: hid, raw: t,
        cmpId: ref && claimNo ? anchorId(idPrefix, claimNo, ref[1]) : null,
        node: <Tag key={key++} id={hid} className={'rr-h rr-h' + level}>{inline(body, `h${key}`, ctx)}</Tag>,
      })
      if (grouped
        ? (level === 1 && body !== 'Novelty Assessment') || (level === 2 && body === 'Novelty summary')
        : level <= 2) toc.push({ id: hid, level, text: body })
      prevNonEmpty = t; i++; continue
    }

    // v4 only: the claim row's verdict, and recorded open points.
    const verdictLine = grouped && VERDICT_LINE.exec(t)
    const verdictMark = verdictLine && assessment(verdictLine[1])
    if (verdictMark) {
      items.push({
        type: 'node', raw: t,
        node: (
          <p key={key++} className="rr-p lay-verdict">
            <strong>Verdict:</strong>{' '}
            <span className={`as-pill ${verdictMark.className}`}>{verdictMark.label}</span>
          </p>
        ),
      })
      prevNonEmpty = t; i++; continue
    }
    const openLine = grouped && OPEN_POINT_LINE.exec(t)
    if (openLine) {
      items.push({
        type: 'node', raw: t,
        node: (
          <p key={key++} className="rr-p lay-open">
            <span className="lay-open-mark" aria-hidden="true">!</span>
            <span>{inline(t, `o${key}`, ctx)}</span>
          </p>
        ),
      })
      prevNonEmpty = t; i++; continue
    }

    // "**Assessment:** …" / "**Status:** …": the verdict gets its colour here, wherever in
    // the document it stands. Only these two labels are classified -- never loose prose.
    const labelled = ASSESSMENT_LINE.exec(t)
    const marked = labelled && assessment(labelled[2])
    if (marked) {
      items.push({
        type: 'node', raw: t,
        node: (
          <p key={key++} className="rr-p as-assess">
            <strong>{labelled[1]}:</strong>{' '}
            <span className={`as-pill ${marked.className}`}>{marked.label}</span>
            {marked.rest ? <span> {inline(marked.rest, `a${key}`, ctx)}</span> : null}
          </p>
        ),
      })
      prevNonEmpty = t; i++; continue
    }

    if (t.startsWith('|')) {
      const rows = []
      while (i < lines.length && lines[i].trim().startsWith('|')) { rows.push(lines[i].trim()); i++ }
      items.push({ type: 'node', node: <Table key={key++} rows={rows} keyPrefix={`t${key}`} ctx={ctx} /> })
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
                    target={resolve(quoteText)} activeId={activeId} onPick={onPick}
                    claim={subMap.has(quoteText) ? claimOf.get(subMap.get(quoteText)) : undefined} />,
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
              <li key={ii} className={it.nested ? 'rr-nested' : undefined}>{inline(it.text, `l${key}-${ii}`, ctx)}</li>
            ))}
          </ul>
        ),
      })
      prevNonEmpty = bullets[bullets.length - 1]?.text || ''
      continue
    }

    const anchorClaim = claimTextFor
    const anchor = anchorClaim && quoteIndex?.claim_anchors?.[String(anchorClaim)]
    claimTextFor = 0
    if (anchor && onPick) {
      items.push({
        type: 'node', raw: t,
        node: (
          <p key={key++} className="rr-p lay-claimtext">
            <a href="#" className={'claim-jump claim-colored' + (activeId === anchor.id ? ' active' : '')}
               style={{ '--claim-color': claimColor(anchorClaim) }}
               title={`Show where the submission states this claim:
“${anchor.text}”`}
               onClick={(e) => { e.preventDefault(); e.stopPropagation(); onPick({ id: anchor.id }) }}>
              {inline(t, `p${key}`, ctx)}
              <span className="claim-jump-mark" aria-hidden="true"> ⤴ PDF</span>
            </a>
          </p>
        ),
      })
      prevNonEmpty = t; i++; continue
    }
    items.push({ type: 'node', raw: t, node: <p key={key++} className="rr-p">{inline(t, `p${key}`, ctx)}</p> })
    prevNonEmpty = t; i++
  }

  if (grouped) return { nodes: renderGrouped(groupReport(items), 'g'), toc }

  // Second pass: fold the level-4 blocks of a comparison into their own tinted boxes,
  // the ones SUB_BLOCKS marks as folded starting closed.
  const foldSub = (list, keyBase) => {
    const acc = []
    let j = 0
    while (j < list.length) {
      const it = list[j]
      const spec = it.type === 'heading' && it.level === 4 ? subBlock(it.text) : null
      if (!spec) { acc.push(it.node); j++; continue }
      const body = []
      let k = j + 1
      while (k < list.length && !(list[k].type === 'heading' && list[k].level <= 4)) {
        body.push(list[k].node); k++
      }
      acc.push(
        <details key={`${keyBase}-s${j}`} id={it.id} open={spec.open}
                 className={`rr-sub blk blk-${spec.kind}`}>
          <summary className="rr-sub-summary">{it.text}</summary>
          <div className="rr-sub-body">{body}</div>
        </details>,
      )
      j = k
    }
    return acc
  }

  // ... and each per-source comparison into a collapsed <details>.
  const nodes = []
  let j = 0
  while (j < items.length) {
    const it = items[j]
    if (it.type === 'heading' && it.level >= 3 && DETAIL_HEADING.test(it.text)) {
      const bodyItems = []
      let k = j + 1
      while (k < items.length && !(items[k].type === 'heading' && items[k].level <= it.level)) {
        bodyItems.push(items[k]); k++
      }
      // The assessment is the one thing a reader cannot see while the section is folded,
      // so the summary line carries it: the section's own words, in the same colour they
      // have inside, not a second judgement.
      const line = bodyItems.map((b) => ASSESSMENT_LINE.exec(b.raw || '')).find(Boolean)
      const mark = line && assessment(line[2])
      nodes.push(
        <details key={`d${j}`} className="rr-detail" id={it.cmpId || it.id}>
          <summary className="rr-detail-summary" id={it.cmpId ? it.id : undefined}>
            <span className="rr-detail-title">{it.text}</span>
            {mark ? <span className={`as-pill ${mark.className}`}>{mark.label}</span> : null}
          </summary>
          <div className="rr-detail-body">{foldSub(bodyItems, `d${j}`)}</div>
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

/** The v4 tree (assessmentStyle.groupReport) as markup. Claims and every fold start
 *  closed; a comparison is shown in full down to its two folded blocks. Each fold carries
 *  the id of its own heading, so a jump or a contents link opens it (jumpToId unfolds every
 *  <details> on the way), and a comparison carries battle_export's #cmp-N-R# anchor. */
function renderGrouped(nodes, keyBase) {
  return nodes.map((n, idx) => {
    const k = `${keyBase}-${idx}`
    if (n.t === 'item') return n.item.node
    if (n.t === 'fold') {
      return (
        <details key={k} id={n.item.id} className={`lay-fold blk blk-${n.kind}`}>
          <summary className="lay-fold-summary">{n.item.text}</summary>
          <div className="lay-fold-body">{renderGrouped(n.body, k)}</div>
        </details>
      )
    }
    if (n.t === 'claim') {
      return (
        <details key={k} className="lay-claim">
          <summary className="lay-claim-summary">
            {n.item.node}
            {n.head.map((h) => h.node)}
          </summary>
          <div className="lay-claim-body">{renderGrouped(n.body, k)}</div>
        </details>
      )
    }
    return (
      <section key={k} id={n.item.cmpId || undefined} className="lay-cmp">
        {n.item.node}
        {n.visible.map((v) => v.node)}
        {renderGrouped(n.folds, k)}
      </section>
    )
  })
}

export default function ReportRenderer({ text, quoteIndex, activeId, onPick, idPrefix = 'r',
                                        showToc = true }) {
  const { nodes, toc } = parseReport(text, quoteIndex, { idPrefix, activeId, onPick })
  return (
    <div className="rr-doc">
      {showToc && toc.length > 1 && (
        <details className="rr-toc" open>
          <summary>Contents</summary>
          <ul>
            {toc.map((h) => (
              <li key={h.id} className={'rr-toc-l' + h.level}>
                <button type="button" className="link" onClick={() => jumpToId(h.id)}>{h.text}</button>
              </li>
            ))}
          </ul>
        </details>
      )}
      <div className="rr-body">{nodes}</div>
    </div>
  )
}
