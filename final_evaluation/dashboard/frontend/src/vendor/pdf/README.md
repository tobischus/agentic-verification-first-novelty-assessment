# Read-only vendor snapshot

`PdfViewer.jsx`, `SplitView.jsx`, `locate.js` in this directory are **unmodified copies**
of `frontend/src/pdf/{PdfViewer,SplitView}.jsx` and `frontend/src/pdf/locate.js` from
commit `755e2600517f91348fa4fd738a1df739815b6e95`.

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
