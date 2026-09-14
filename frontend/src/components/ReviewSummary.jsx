import { useEffect, useState } from "react";
import { api } from "../api";
import SplitView from "../pdf/SplitView.jsx";
import PdfViewer, { colorFor } from "../pdf/PdfViewer.jsx";

// The Summary tab renders `/review/export`'s text -- the exact artifact used in the
// system comparison -- and NOTHING else: no synthesis, no extra framing, no fields the
// export itself does not print. What this file adds is presentation only: headings,
// tables and blockquotes instead of one <pre>, and quotes that jump to their passage in
// the PDF the same way the Review tab's quotes do. The content is the export's; the
// interactivity is a side channel (`/review/quote_index`, see battle_export.quote_index)
// that maps each VERIFIED blockquote's own text back to a document and a highlight id.
// Content and interactivity can never drift apart on the CONTENT side, because the
// content is never re-typed here -- it is parsed, not regenerated.

const norm = (s) => (s || "").replace(/\s+/g, " ").trim();
// Strip the curly quotes _quote() wraps a span in, so the inner text matches the index's
// key exactly (the index normalises with the same ' '.join(text.split()) rule).
const unquote = (s) => norm(s).replace(/^[“"]/, "").replace(/[”"]$/, "");

/** **bold**, [text](url) / [text](<url>), and plain text -> inline React nodes. */
function inline(text, keyPrefix) {
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
    last = re.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** A rendered quote block: clickable + coloured when the index resolves it to a
 *  document, plain (but still visually a quote) when it does not -- e.g. a span the
 *  export itself marked "Not confirmed verbatim", which the index never indexes. */
function Quote({ text, target, activeId, onPick }) {
  const clickable = !!target;
  const active = clickable && activeId === target.id;
  return (
    <blockquote
      className={"rz-quote" + (clickable ? " qjump" : "") + (active ? " active" : "")}
      onClick={clickable ? () => onPick(target) : undefined}
      title={clickable ? "Show this passage in the PDF" : undefined}
    >
      <span className="rz-qmark" title="Verified verbatim in its source">
        ✓
      </span>
      <span className="rz-qtext">{text}</span>
    </blockquote>
  );
}

function Table({ rows, keyPrefix }) {
  const cells = (line) =>
    line
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((c) => c.trim().replace(/&#124;/g, "|"));
  const head = cells(rows[0]);
  const body = rows.slice(2).map(cells); // rows[1] is the |---|---| separator
  return (
    <div className="se-table-wrap">
      <table className="se-table">
        <thead>
          <tr>
            {head.map((h, i) => (
              <th key={i}>{inline(h, `${keyPrefix}-h${i}`)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((r, ri) => (
            <tr key={ri}>
              {r.map((c, ci) => (
                <td key={ci}>{inline(c, `${keyPrefix}-${ri}-${ci}`)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Parse the export text into React blocks, resolving each blockquote against the
 *  quote index as it walks past the "### R# — Title" heading that names which paper's
 *  passages follow -- see quote_index's own docstring for why text alone is the key. */
function renderExport(text, index, activeId, onPick) {
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

  const out = [];
  let currentPaper = null;
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
        t === "## Related work examined") {
      currentPaper = null;
    } else if (refHead) {
      currentPaper = refToPaper[refHead[1]] || null;
    }

    if (t === "---") {
      out.push(<hr key={key++} className="se-hr" />);
      i++;
      continue;
    }

    const heading = t.match(/^(#{1,5})\s+(.*)$/);
    if (heading) {
      const level = heading[1].length;
      const Tag = `h${Math.min(level + 1, 6)}`; // export's h1 is the doc title, not the page's
      out.push(
        <Tag key={key++} className={"se-h se-h" + level}>
          {inline(heading[2], `h${key}`)}
        </Tag>,
      );
      i++;
      continue;
    }

    if (t.startsWith("|")) {
      const rows = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        rows.push(lines[i].trim());
        i++;
      }
      out.push(<Table key={key++} rows={rows} keyPrefix={`t${key}`} />);
      continue;
    }

    if (t.startsWith("> ")) {
      const quoteText = unquote(t.slice(2));
      const target = resolve(quoteText, currentPaper);
      out.push(
        <Quote
          key={key++}
          text={quoteText}
          target={target}
          activeId={activeId}
          onPick={onPick}
        />,
      );
      i++;
      continue;
    }

    if (/^- /.test(t) || /^  - /.test(t)) {
      const items = [];
      while (i < lines.length && /^\s*- /.test(lines[i])) {
        const nested = /^\s\s/.test(lines[i]);
        items.push({ nested, text: lines[i].trim().replace(/^- /, "") });
        i++;
      }
      out.push(
        <ul key={key++} className="se-list">
          {items.map((it, ii) => (
            <li key={ii} className={it.nested ? "se-nested" : undefined}>
              {inline(it.text, `l${key}-${ii}`)}
            </li>
          ))}
        </ul>,
      );
      continue;
    }

    out.push(
      <p key={key++} className="se-p">
        {inline(t, `p${key}`)}
      </p>,
    );
    i++;
  }
  return out;
}

export default function ReviewSummary({ submissionId, active }) {
  const [text, setText] = useState(null);
  const [index, setIndex] = useState(null);
  const [err, setErr] = useState("");
  const [reader, setReader] = useState({ paperId: null, focusId: null });

  const load = () => {
    Promise.all([api.reviewExport(submissionId), api.quoteIndex(submissionId)])
      .then(([t, idx]) => {
        setText(t);
        setIndex(idx);
        setErr("");
      })
      .catch((e) => {
        const msg = String(e);
        if (msg.includes("no claims computed") || msg.includes("404")) {
          setText("");
          setIndex({ submission: [], papers: {}, refs: {} });
          setErr("");
        } else setErr(msg);
      });
  };

  useEffect(load, [submissionId]);
  useEffect(() => {
    if (active) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  if (err)
    return (
      <div className="panel">
        <div className="error">{err}</div>
      </div>
    );
  if (text === null) return <div className="panel">Loading summary…</div>;

  if (!text) {
    return (
      <div className="panel review-summary">
        <div className="muted">
          No claims have been reviewed yet. Open the <strong>Review</strong> tab
          and run the claim-level review first.
        </div>
      </div>
    );
  }

  const onPick = (target) => setReader({ paperId: target.paperId, focusId: target.id });

  const paperIds = Object.keys(index.papers || {});
  const readerPaper = reader.paperId ? index.papers[reader.paperId] : null;
  const paperColor = {};
  paperIds.forEach((pid, i) => {
    paperColor[pid] = colorFor(i + 1);
  });

  const highlights = readerPaper
    ? readerPaper.quotes.map((q) => ({ id: q.id, text: q.text, color: paperColor[reader.paperId] }))
    : (index.submission || []).map((q) => ({ id: q.id, text: q.text, color: colorFor(0) }));

  const readerUrl = reader.paperId
    ? api.paperPdfUrl(submissionId, reader.paperId)
    : api.pdfUrl(submissionId);

  const panel = (
    <div className="panel review-summary se-export">
      {renderExport(text, index, reader.focusId, onPick)}
    </div>
  );

  const viewer = (
    <div className="pdfpane">
      <div className="pdfpicker">
        <select
          value={reader.paperId || ""}
          onChange={(e) =>
            setReader({ paperId: e.target.value || null, focusId: null })
          }
        >
          <option value="">The submission</option>
          {paperIds.map((pid) => (
            <option key={pid} value={pid}>
              {index.papers[pid].title}
            </option>
          ))}
        </select>
      </div>
      <PdfViewer
        key={readerUrl}
        url={readerUrl}
        highlights={highlights}
        focusId={reader.focusId}
      />
    </div>
  );

  return <SplitView storageKey="summary" left={panel} right={viewer} />;
}
