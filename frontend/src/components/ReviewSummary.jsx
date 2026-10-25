import { useEffect, useState } from "react";
import { api } from "../api";
import SplitView from "../pdf/SplitView.jsx";
import PdfViewer, { colorFor } from "../pdf/PdfViewer.jsx";
import { claimOfPassages } from "./assessmentStyle.js";
import { DIM, claimColor, renderExport } from "./exportRender.jsx";

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

  const claimOf = claimOfPassages(text, index);
  const shade = (id, color) => (reader.focusId && id !== reader.focusId ? color + DIM : color);
  const highlights = readerPaper
    ? readerPaper.quotes.map((q) => ({
        id: q.id, text: q.text, color: shade(q.id, paperColor[reader.paperId]),
      }))
    : (index.submission || []).map((q) => ({
        id: q.id,
        text: q.text,
        color: shade(q.id, claimOf.has(q.id) ? claimColor(claimOf.get(q.id)) : colorFor(0)),
      }));

  const readerUrl = reader.paperId
    ? api.paperPdfUrl(submissionId, reader.paperId)
    : api.pdfUrl(submissionId);

  const panel = (
    <div className="panel review-summary se-export">
      {renderExport(text, index, reader.focusId, onPick, claimOf)}
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
