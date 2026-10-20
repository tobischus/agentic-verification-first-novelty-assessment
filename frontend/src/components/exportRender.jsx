// The export renderer, shared by the Summary tab (the whole report) and the Review tab (one
// claim of it). Moved out of ReviewSummary.jsx unchanged, so the two tabs cannot drift
// apart: both show `/review/export`'s own text, parsed, never re-typed. The only additions
// are options -- a DOM id prefix per tab, the v4 layout flag for a slice, and claim cards
// that start open -- plus the helpers that cut one claim out of the report.
import { colorFor } from "../pdf/PdfViewer.jsx";
import {
  ASSESSMENT_LINE,
  CLAIM_HEADING,
  DETAIL_HEADING,
  OPEN_POINT_LINE,
  VERDICT_LINE,
  anchorId,
  assessment,
  groupReport,
  isGroupedLayout,
  jumpToId,
  resolveAnchor,
  subBlock,
} from "./assessmentStyle.js";

export const norm = (s) => (s || "").replace(/\s+/g, " ").trim();
// Strip the curly quotes _quote() wraps a span in, so the inner text matches the index's
// key exactly (the index normalises with the same ' '.join(text.split()) rule).
export const unquote = (s) => norm(s).replace(/^[“"]/, "").replace(/[”"]$/, "");

// One colour per claim, shared by the claim's text on the left and every submission
// passage filed under it in the PDF -- with one colour for all, six claim anchors on the
// same page could not be told apart.
export const claimColor = (n) => colorFor(n - 1);
// Highlights that are not the one just jumped to are drawn at this alpha (hex suffix on
// the '#rrggbb' palette), so the target stands out while keeping its claim's hue.
export const DIM = "73";

/** **bold**, [text](url) / [text](<url>), the export's own "#cmp-<claim>-<ref>" jump
 *  links, and plain text -> inline React nodes. */
export function inline(text, keyPrefix, idPrefix = "se") {
  const out = [];
  const re = /\*\*(.+?)\*\*|\[([^\]]+)\]\(<?([^()>]+)>?\)/g;
  let last = 0,
    m,
    i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    if (m[1] !== undefined) {
      out.push(<strong key={`${keyPrefix}-b${i++}`}>{m[1]}</strong>);
    } else {
      const target = resolveAnchor(idPrefix, m[3]);
      if (target) {
        out.push(
          <a
            key={`${keyPrefix}-j${i++}`}
            className="as-jump"
            href={`#${target}`}
            onClick={(e) => {
              e.preventDefault();
              jumpToId(target);
            }}
          >
            {m[2]}
          </a>,
        );
      } else {
        out.push(
          <a
            key={`${keyPrefix}-a${i++}`}
            href={m[3]}
            target="_blank"
            rel="noreferrer"
          >
            {m[2]}
          </a>,
        );
      }
    }
    last = re.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** A rendered quote block: clickable + coloured when the index resolves it to a
 *  document, plain (but still visually a quote) when it does not -- e.g. a span the
 *  export itself marked "Not confirmed verbatim", which the index never indexes. */
export function Quote({ text, target, activeId, onPick, color, claim }) {
  const clickable = !!target;
  const active = clickable && activeId === target.id;
  return (
    <blockquote
      className={"rz-quote" + (clickable ? " qjump" : "") + (active ? " active" : "")}
      onClick={clickable ? () => onPick(target) : undefined}
      title={clickable ? "Show this passage in the PDF" : undefined}
    >
      {color && (
        <span
          className="qswatch"
          style={{ background: color }}
          title={claim ? `Highlighted in this colour in the PDF (claim ${claim})` : undefined}
        />
      )}
      <span className="rz-qmark" title="Verified verbatim in its source">
        ✓
      </span>
      <span className="rz-qtext">{text}</span>
    </blockquote>
  );
}

/** A table, with assessment cells coloured and any row carrying substantial-or-higher
 *  overlap marked. Only a cell that is ENTIRELY an assessment phrase is classified, so a
 *  paper title or a version date is never tinted by accident. */
function Table({ rows, keyPrefix, idPrefix }) {
  const cells = (line) =>
    line
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((c) => c.trim().replace(/&#124;/g, "|"));
  // A linked assessment reads "[partial overlap · material evidence](#cmp-2-R7)"; the
  // classification looks at the label, the link keeps working either way.
  const bare = (c) => c.replace(/^\[([^\]]+)\]\(#[^)]*\)$/, "$1");
  const head = cells(rows[0]);
  const body = rows.slice(2).map(cells); // rows[1] is the |---|---| separator
  return (
    <div className="se-table-wrap">
      <table className="se-table">
        <thead>
          <tr>
            {head.map((h, i) => (
              <th key={i}>{inline(h, `${keyPrefix}-h${i}`, idPrefix)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((r, ri) => {
            const marks = r.map((c) => assessment(bare(c), { whole: true }));
            return (
              <tr
                key={ri}
                className={
                  marks.some((a) => a && a.strong) ? "as-cell-row" : undefined
                }
              >
                {r.map((c, ci) => (
                  <td
                    key={ci}
                    className={
                      marks[ci] ? `as-cell ${marks[ci].className}` : undefined
                    }
                  >
                    {inline(c, `${keyPrefix}-${ri}-${ci}`, idPrefix)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Parse the export text into React blocks, resolving each blockquote against the
 *  quote index as it walks past the "### R# — Title" heading that names which paper's
 *  passages follow -- see quote_index's own docstring for why text alone is the key.
 *
 *  Two passes, like the dashboard's renderer: the first turns lines into items, the
 *  second folds the level-4 blocks of a comparison into their own boxes. Grouping needs
 *  to know where the next heading starts, and nothing is dropped in either pass -- a
 *  folded block still holds its full text. */
export function renderExport(text, index, activeId, onPick, claimOf = new Map(), opts = {}) {
  // idPrefix keeps DOM ids unique when two tabs render the same export at once;
  // grouped lets a caller that renders one claim's slice keep the v4 layout, whose
  // marker heading the slice does not contain; openClaims starts claim cards open.
  const { idPrefix = "se", openClaims = false } = opts;
  const lines = (text || "").split("\n");
  const subMap = new Map((index?.submission || []).map((q) => [q.text, q.id]));
  const refToPaper = {};
  Object.entries(index?.refs || {}).forEach(([pid, ref]) => {
    refToPaper[ref] = pid;
  });
  const papMap = (pid) =>
    new Map((index?.papers?.[pid]?.quotes || []).map((q) => [q.text, q.id]));

  const resolve = (quoteText, currentPaper) => {
    if (currentPaper) {
      const m = papMap(currentPaper);
      if (m.has(quoteText)) return { paperId: currentPaper, id: m.get(quoteText) };
    }
    if (subMap.has(quoteText)) return { paperId: null, id: subMap.get(quoteText) };
    return null;
  };

  const items = [];
  // v4 exports are grouped by the shared rules in assessmentStyle.js (same as the study
  // dashboard); anything older keeps the rendering below unchanged.
  const grouped = opts.grouped ?? isGroupedLayout(text);
  let currentPaper = null;
  let claimNo = 0;
  let claimTextFor = 0;
  let i = 0,
    key = 0;
  while (i < lines.length) {
    const line = lines[i];
    const t = line.trim();

    if (!t) {
      i++;
      continue;
    }

    // Context: which paper (if any) the following passages belong to.
    const refHead = t.match(/^###\s+(R\d+)\s+—\s+(.+)$/);
    if (/^#\s+Claim\s+\d+\s+—\s+Review$/.test(t) || t === "## Extracted claims" ||
        t === "## Related work examined" || (grouped && /^#\s/.test(t))) {
      currentPaper = null;
    } else if (refHead) {
      currentPaper = refToPaper[refHead[1]] || null;
    }

    if (t === "---") {
      items.push({ type: "node", hr: grouped, node: <hr key={key++} className="se-hr" /> });
      i++;
      continue;
    }

    const heading = t.match(/^(#{1,5})\s+(.*)$/);
    if (heading) {
      const level = heading[1].length;
      const body = heading[2];
      const Tag = `h${Math.min(level + 1, 6)}`; // export's h1 is the doc title, not the page's
      // The claim heading fixes which claim the "### R# — ..." sections below belong to;
      // together they are battle_export._anchor()'s two halves, so a linked assessment in
      // the overview tables lands on the comparison it names.
      const claim = CLAIM_HEADING.exec(body);
      if (claim) claimNo = Number(claim[1]);
      // v4.4: the claim's own text, the next paragraph, links to its anchor in the PDF.
      claimTextFor = grouped && claim ? claimNo : 0;
      const ref = DETAIL_HEADING.exec(body);
      const cmpId = ref && claimNo ? anchorId(idPrefix, claimNo, ref[1]) : null;
      items.push({
        type: "heading",
        level,
        text: body,
        raw: t,
        node: (
          <Tag key={key++} id={cmpId || undefined} className={"se-h se-h" + level}>
            {inline(body, `h${key}`, idPrefix)}
          </Tag>
        ),
      });
      i++;
      continue;
    }

    // v4 only: the claim row's verdict, and recorded open points.
    const verdictLine = grouped && VERDICT_LINE.exec(t);
    const verdictMark = verdictLine && assessment(verdictLine[1]);
    if (verdictMark) {
      items.push({
        type: "node",
        raw: t,
        node: (
          <p key={key++} className="se-p lay-verdict">
            <strong>Verdict:</strong>{" "}
            <span className={`as-pill ${verdictMark.className}`}>{verdictMark.label}</span>
          </p>
        ),
      });
      i++;
      continue;
    }
    const openLine = grouped && OPEN_POINT_LINE.exec(t);
    if (openLine) {
      items.push({
        type: "node",
        raw: t,
        node: (
          <p key={key++} className="se-p lay-open">
            <span className="lay-open-mark" aria-hidden="true">!</span>
            <span>{inline(t, `o${key}`, idPrefix)}</span>
          </p>
        ),
      });
      i++;
      continue;
    }

    // "**Assessment:** …" / "**Status:** …": the assessment gets its colour here, wherever
    // in the document it stands. Only these two labels are classified -- never loose prose.
    const labelled = ASSESSMENT_LINE.exec(t);
    const marked = labelled && assessment(labelled[2]);
    if (marked) {
      items.push({
        type: "node",
        raw: t,
        node: (
          <p key={key++} className="se-p as-assess">
            <strong>{labelled[1]}:</strong>{" "}
            <span className={`as-pill ${marked.className}`}>{marked.label}</span>
            {marked.rest ? <span> {inline(marked.rest, `a${key}`, idPrefix)}</span> : null}
          </p>
        ),
      });
      i++;
      continue;
    }

    if (t.startsWith("|")) {
      const rows = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        rows.push(lines[i].trim());
        i++;
      }
      items.push({
        type: "node",
        node: <Table key={key++} rows={rows} keyPrefix={`t${key}`} idPrefix={idPrefix} />,
      });
      continue;
    }

    if (t.startsWith("> ")) {
      const quoteText = unquote(t.slice(2));
      const target = resolve(quoteText, currentPaper);
      // Only a submission passage carries its claim's colour: a prior-work quote is
      // highlighted in its own paper's PDF, in that paper's colour.
      const claim = target && !target.paperId ? claimOf.get(target.id) : undefined;
      items.push({
        type: "node",
        node: (
          <Quote
            key={key++}
            text={quoteText}
            target={target}
            activeId={activeId}
            onPick={onPick}
            claim={claim}
            color={claim ? claimColor(claim) : undefined}
          />
        ),
      });
      i++;
      continue;
    }

    if (/^- /.test(t) || /^  - /.test(t)) {
      const bullets = [];
      while (i < lines.length && /^\s*- /.test(lines[i])) {
        const nested = /^\s\s/.test(lines[i]);
        bullets.push({ nested, text: lines[i].trim().replace(/^- /, "") });
        i++;
      }
      items.push({
        type: "node",
        node: (
          <ul key={key++} className="se-list">
            {bullets.map((it, ii) => (
              <li key={ii} className={it.nested ? "se-nested" : undefined}>
                {inline(it.text, `l${key}-${ii}`, idPrefix)}
              </li>
            ))}
          </ul>
        ),
      });
      continue;
    }

    const anchorClaim = claimTextFor;
    const anchor = anchorClaim && index?.claim_anchors?.[String(anchorClaim)];
    claimTextFor = 0;
    if (anchor && onPick) {
      items.push({
        type: "node",
        raw: t,
        node: (
          <p key={key++} className="se-p lay-claimtext">
            <a
              href="#"
              className={"claim-jump claim-colored" + (activeId === anchor.id ? " active" : "")}
              style={{ "--claim-color": claimColor(anchorClaim) }}
              title={`Show where the submission states this claim:
“${anchor.text}”`}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onPick({ paperId: null, id: anchor.id });
              }}
            >
              {inline(t, `p${key}`, idPrefix)}
              <span className="claim-jump-mark" aria-hidden="true"> ⤴ PDF</span>
            </a>
          </p>
        ),
      });
      i++;
      continue;
    }
    items.push({
      type: "node",
      raw: t,
      node: (
        <p key={key++} className="se-p">
          {inline(t, `p${key}`, idPrefix)}
        </p>
      ),
    });
    i++;
  }

  if (grouped) return renderGrouped(groupReport(items), "g", { openClaims });

  // Second pass: each level-4 block of a comparison becomes its own tinted box, folded
  // where SUB_BLOCKS says so. Folding hides no text -- it is one click from open.
  const out = [];
  let j = 0;
  while (j < items.length) {
    const it = items[j];
    const spec =
      it.type === "heading" && it.level === 4 ? subBlock(it.text) : null;
    if (!spec) {
      out.push(it.node);
      j++;
      continue;
    }
    const body = [];
    let k = j + 1;
    while (k < items.length && !(items[k].type === "heading" && items[k].level <= 4)) {
      body.push(items[k].node);
      k++;
    }
    out.push(
      <details key={`s${j}`} open={spec.open} className={`se-sub blk blk-${spec.kind}`}>
        <summary className="se-sub-summary">{it.text}</summary>
        <div className="se-sub-body">{body}</div>
      </details>,
    );
    j = k;
  }
  return out;
}

/** The v4 tree as markup: claims and every fold start closed, a comparison is shown down
 *  to its two folded blocks. A comparison's jump anchor stays on its heading (set in the
 *  first pass), and jumpToId unfolds every <details> it sits in. */
export function renderGrouped(nodes, keyBase, opts = {}) {
  return nodes.map((n, idx) => {
    const k = `${keyBase}-${idx}`;
    if (n.t === "item") return n.item.node;
    if (n.t === "fold") {
      return (
        <details key={k} className={`lay-fold blk blk-${n.kind}`}>
          <summary className="lay-fold-summary">{n.item.text}</summary>
          <div className="lay-fold-body">{renderGrouped(n.body, k, opts)}</div>
        </details>
      );
    }
    if (n.t === "claim") {
      return (
        <details key={k} className="lay-claim" open={opts.openClaims || undefined}>
          <summary className="lay-claim-summary">
            {n.item.node}
            {n.head.map((h) => h.node)}
          </summary>
          <div className="lay-claim-body">{renderGrouped(n.body, k, opts)}</div>
        </details>
      );
    }
    return (
      <section key={k} className="lay-cmp">
        {n.item.node}
        {n.visible.map((v) => v.node)}
        {renderGrouped(n.folds, k, opts)}
      </section>
    );
  });
}

/** One claim's section of the report: from its "# Claim N — Review" heading up to the
 *  next level-1 heading. Empty when the report has no such claim (not computed yet). */
export function claimSection(text, claimNo) {
  const lines = (text || "").split("\n");
  const start = lines.findIndex((l) => {
    const h = l.trim().match(/^#\s+(.*)$/);
    const c = h && CLAIM_HEADING.exec(h[1]);
    return c && Number(c[1]) === claimNo;
  });
  if (start < 0) return "";
  let end = start + 1;
  while (end < lines.length && !/^#\s/.test(lines[end].trim())) end++;
  return lines.slice(start, end).join("\n");
}

/** The quoted passages a piece of the report prints, as the quote index keys them. */
export function quotedTexts(text) {
  return new Set(
    (text || "")
      .split("\n")
      .map((l) => l.trim())
      .filter((t) => t.startsWith("> "))
      .map((t) => unquote(t.slice(2))),
  );
}

/** The source ids ("R7") whose detailed comparison a piece of the report contains. */
export function detailRefs(text) {
  const out = [];
  for (const l of (text || "").split("\n")) {
    const m = l.trim().match(/^###\s+(R\d+)\s+—\s+/);
    if (m && !out.includes(m[1])) out.push(m[1]);
  }
  return out;
}
