# Read-only vendor snapshot

`PdfViewer.jsx`, `SplitView.jsx`, `locate.js` in this directory are **unmodified copies**
of `frontend/src/pdf/{PdfViewer,SplitView}.jsx` and `frontend/src/pdf/locate.js` from
commit `755e2600517f91348fa4fd738a1df739815b6e95`, with `PdfViewer.jsx` and `locate.js`
re-copied once since (2026-09-23, content version reviewer-v4.4):

- `PdfViewer.jsx` takes each highlight's colour from the current `highlights` prop and
  draws the focused passage first, so the passage a reviewer jumped to can be drawn
  stronger than the rest.
- `locate.js` marks a quote from its first to its last character instead of whole text
  lines, and snaps the matched range to the quote's own first and last three words.
  Which quotes are found is unchanged (536/538 over the study's submission quotes, before
  and after); the words marked outside the quote dropped from 48 before / 107 after to
  0 / 0.

The viewer's styles are NOT part of the snapshot: they live in the main app's
`styles.css`, and the rules it needs (`.pdfpage`, `.pdfhl`, ...) are repeated in this
app's `src/styles.css`. Without them the highlight boxes are not laid over the page.

They are copied rather than imported across the two independent Vite apps so that:

- the study dashboard can be built and deployed with no dependency on the main
  `frontend/` package or its dev server;
- the main app's PDF viewer is never touched by this study's build — a change here
  cannot break claim review, and a change there is not silently picked up here.

**Do not edit these three files.** If the main viewer changes and the study should pick
up the change, re-copy it deliberately (same command used to create this snapshot:
`cp frontend/src/pdf/{PdfViewer,SplitView}.jsx frontend/src/pdf/locate.js
final_evaluation/dashboard/frontend/src/vendor/pdf/`) and update the commit hash above.
Everything else in `dashboard/frontend/` is this study's own code.
