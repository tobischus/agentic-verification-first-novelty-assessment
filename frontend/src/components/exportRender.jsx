// Renders the report text of /review/export, for the whole report or one claim.
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
export const unquote = (s) => norm(s).replace(/^[“"]/, "").replace(/[”"]$/, "");

export const claimColor = (n) => colorFor(n - 1);
export const DIM = "73";

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

function Table({ rows, keyPrefix, idPrefix }) {
  const cells = (line) =>
    line
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((c) => c.trim().replace(/&#124;/g, "|"));
  const bare = (c) => c.replace(/^\[([^\]]+)\]\(#[^)]*\)$/, "$1");
  const head = cells(rows[0]);
  const body = rows.slice(2).map(cells);
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

export function renderExport(text, index, activeId, onPick, claimOf = new Map(), opts = {}) {
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
      const Tag = `h${Math.min(level + 1, 6)}`;
      const claim = CLAIM_HEADING.exec(body);
      if (claim) claimNo = Number(claim[1]);
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

export function quotedTexts(text) {
  return new Set(
    (text || "")
      .split("\n")
      .map((l) => l.trim())
      .filter((t) => t.startsWith("> "))
      .map((t) => unquote(t.slice(2))),
  );
}

export function detailRefs(text) {
  const out = [];
  for (const l of (text || "").split("\n")) {
    const m = l.trim().match(/^###\s+(R\d+)\s+—\s+/);
    if (m && !out.includes(m[1])) out.push(m[1]);
  }
  return out;
}
