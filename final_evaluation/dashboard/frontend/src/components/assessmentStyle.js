// How the export's own assessment wording becomes colour, and how its jump links resolve.
//
// This file exists TWICE, byte-identical:
//
//   frontend/src/components/assessmentStyle.js                          (Summary tab)
//   final_evaluation/dashboard/frontend/src/components/assessmentStyle.js  (study UI)
//
// The two renderers live in independent Vite apps and cannot import each other (see
// ReportRenderer.jsx's header for why the dashboard copies rather than imports). Keeping
// the RULES in one file per app, with the two files identical, makes the duplication
// checkable instead of hopeful: final_evaluation/tests/test_renderer_parity.py fails if
// they drift. A report coloured one way in the pipeline's Summary tab and another way in
// the study dashboard would be a second, silent way for the two views to disagree about
// the same document.
//
// Nothing here judges anything. Every phrase below is one battle_export already prints:
// the degree words come from verdict.DEGREE_LABEL via battle_export._related_cell (which
// falls through to the raw degree for `superficial`/`none`), the evidence words from
// battle_export._EC_PHRASE, the three verdict phrases from verdict.VERDICT_LABEL. This
// module reads the label the export wrote and picks a colour for it.

const norm = (s) => (s || '').replace(/\s+/g, ' ').trim();

const DEGREES = {
  'same contribution': 'same',
  'substantial overlap': 'substantial',
  'partial overlap': 'partial',
  superficial: 'weak',
  'no overlap': 'weak',
  none: 'weak',
  'not compared': 'unknown',
  'not assessed': 'unknown',
};

const EVIDENCE = {
  'material evidence': 'material',
  nonmaterial: 'nonmaterial',
  'insufficient evidence': 'insufficient',
  'no evidence check': 'nocheck',
};

const VERDICTS = {
  'challenged by prior work': 'challenged',
  'not challenged in the examined literature': 'unchallenged',
  uncertain: 'uncertain',
};

// Longest phrase first, so `no overlap` can never lose to `none` (or `insufficient
// evidence` to a shorter prefix) through alternation order.
const alt = (map) =>
  Object.keys(map)
    .sort((a, b) => b.length - a.length)
    .map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('|');

const DEGREE_RE = new RegExp(`^(${alt(DEGREES)})(?:\\s*·\\s*(${alt(EVIDENCE)}))?`, 'i');
const VERDICT_RE = new RegExp(`^(${alt(VERDICTS)})`, 'i');
const EVIDENCE_RE = new RegExp(`^(${alt(EVIDENCE)})`, 'i');

/** The label lines whose value is an assessment: "**Assessment:** …", "**Status:** …". */
export const ASSESSMENT_LINE = /^\*\*(Assessment|Status):\*\*\s*(.+)$/;

/** Classes for one assessment phrase, or null when `text` does not start with one.
 *
 *  Returns { label, rest, degree, evidence, verdict, strong, className }. `label` is the
 *  phrase itself (a single trailing period absorbed, so a claim-level verdict reads as one
 *  sentence) and `rest` is whatever followed it, untouched.
 *
 *  `whole: true` additionally requires the phrase to BE the entire string. Use it wherever
 *  a false positive would colour something that is not an assessment at all -- a table
 *  cell may equally hold a paper title or a version date.
 *
 *  Two dimensions, never collapsed into one: `degree`/`verdict` is how much prior work was
 *  found to overlap, `evidence` is whether an evidence check backs that up. The stylesheets
 *  render the second as a dashed rather than solid outline, so an inconclusive or missing
 *  check cannot pass for a secured result -- the same reason the export prints both parts.
 */
export function assessment(text, { whole = false } = {}) {
  const s = norm(text);
  let degree = null;
  let evidence = null;
  let verdict = null;
  let m = s.match(DEGREE_RE);
  if (m) {
    degree = DEGREES[m[1].toLowerCase()];
    evidence = m[2] ? EVIDENCE[m[2].toLowerCase()] : null;
  } else if ((m = s.match(VERDICT_RE))) {
    verdict = VERDICTS[m[1].toLowerCase()];
  } else if ((m = s.match(EVIDENCE_RE))) {
    evidence = EVIDENCE[m[1].toLowerCase()];
  } else {
    return null;
  }
  let cut = m[0].length;
  if (s[cut] === '.') cut += 1;
  const label = s.slice(0, cut);
  const rest = s.slice(cut).trim();
  if (whole && rest) return null;
  const strong = degree === 'same' || degree === 'substantial' || verdict === 'challenged';
  const className = [
    'as',
    degree && `as-${degree}`,
    verdict && `vd-${verdict}`,
    evidence && `ev-${evidence}`,
    strong && 'as-strong',
  ]
    .filter(Boolean)
    .join(' ');
  return { label, rest, degree, evidence, verdict, strong, className };
}

/** "# Claim 2 — Review" and "### R7 — Title": the two headings an anchor is built from. */
export const CLAIM_HEADING = /^Claim\s+(\d+)\s+[—-]\s+Review$/;
export const DETAIL_HEADING = /^(R\d+)\s+[—-]\s+/;
const ANCHOR_HREF = /^#(cmp-\d+-R\d+)$/;

/** battle_export._anchor()'s scheme, resolved to a DOM id for ONE rendered copy.
 *  The study dashboard shows two reports side by side, both containing "#cmp-2-R7", so a
 *  click has to land in the panel it was made in -- hence the per-panel prefix. */
export const anchorId = (idPrefix, claimNo, ref) => `${idPrefix}-cmp-${claimNo}-${ref}`;

export const resolveAnchor = (idPrefix, href) => {
  const m = ANCHOR_HREF.exec(href || '');
  return m ? `${idPrefix}-${m[1]}` : null;
};

/** Which claim each submission passage belongs to, as a Map from the quote index's
 *  passage id to a claim number: the claim it anchors (`claim_anchors`), else the first
 *  claim under whose "Claim N — Review" heading the report quotes it. Both apps colour a
 *  passage by this, on the left and in the PDF alike, so the two cannot disagree. It is
 *  read from the report text itself, the same headings the renderers walk. */
export function claimOfPassages(text, index) {
  const out = new Map();
  Object.entries(index?.claim_anchors || {}).forEach(([n, a]) => out.set(a.id, Number(n)));
  const sub = new Map((index?.submission || []).map((q) => [q.text, q.id]));
  let claimNo = 0;
  for (const line of (text || '').split('\n')) {
    const t = line.trim();
    const h = t.match(/^#{1,5}\s+(.*)$/);
    if (h) {
      const c = CLAIM_HEADING.exec(h[1]);
      if (c) claimNo = Number(c[1]);
      continue;
    }
    if (!claimNo || !t.startsWith('> ')) continue;
    // _quote()'s curly quotes off, whitespace as the index normalises it
    const id = sub.get(norm(t.slice(2)).replace(/^[“"]/, '').replace(/[”"]$/, ''));
    if (id && !out.has(id)) out.set(id, claimNo);
  }
  return out;
}

/** Scroll to a link target, unfolding everything it is folded inside.
 *  A jump into a collapsed section that stays collapsed looks like a broken link. */
export function jumpToId(id) {
  const el = typeof document === 'undefined' ? null : document.getElementById(id);
  if (!el) return false;
  for (let n = el; n; n = n.parentElement) if (n.tagName === 'DETAILS') n.open = true;
  el.scrollIntoView({ block: 'start', behavior: 'smooth' });
  el.classList.add('as-flash');
  setTimeout(() => el.classList.remove('as-flash'), 1500);
  return true;
}

/** The level-4 blocks of one per-source comparison, and which start folded.
 *
 *  Open: what the assessment rests on -- the comparison's own three fields, and the
 *  evidence pairs the check accepted. Folded: the orientation ("what does this prior paper
 *  do?"), the candidate pairs the check did NOT use, and the check's own bookkeeping.
 *  Folding drops no text and adds none; every block is one click from open.
 */
export const SUB_BLOCKS = [
  { re: /^prior work summary$/i, kind: 'priorwork', open: false },
  { re: /^comparison$/i, kind: 'comparison', open: true },
  { re: /^evidence pairs$/i, kind: 'pairs', open: true },
  { re: /^pairs not used to support overlap\b/i, kind: 'unused', open: false },
  { re: /^evidence-check assessment$/i, kind: 'check', open: false },
];

export const subBlock = (text) => SUB_BLOCKS.find((s) => s.re.test(norm(text))) || null;

// ---------------------------------------------------------------------------------------
// Report layout v4 (battle_export EXPORT_LAYOUT_VERSION "reviewer-v4.0").
//
// The export is plain text with headings; which parts start folded is decided HERE, once,
// for both apps. Folding drops nothing: every folded block keeps its full text, the
// markdown carries all of it, and a jump link opens every block its target sits in.
//
// Recognised by the "# Metadata" section v4 always ends with. Older frozen reports (the
// pilot's v3.x) do not have it and keep being rendered by the older rules above, so a
// report that has already been rated is never shown in a layout it was not rated in.

export const isGroupedLayout = (text) =>
  /^# (Metadata|How to read the assessments)\s*$/m.test(text || '');

/** "**Verdict:** …" is the claim row's verdict; "**Open point(s):** …" a recorded open point. */
export const VERDICT_LINE = /^\*\*Verdict:\*\*\s*(.+)$/;
export const OPEN_POINT_LINE = /^\*\*Open points?:\*\*\s*(.+)$/;

// Level-1 sections other than claims: folded.
const TOP_FOLDS = [
  { re: /^how to read the assessments$/i, kind: 'legend' },
  { re: /^related work examined$/i, kind: 'matrix' },
  { re: /^metadata$/i, kind: 'meta' },
];
// Level-2 sections inside a claim: folded (the claim-level assessment stays open).
const CLAIM_FOLDS = [
  { re: /^submission passages$/i, kind: 'passages' },
  { re: /^coverage and limitations$/i, kind: 'coverage' },
];
// Level-4 blocks inside one comparison: both folded.
const CMP_FOLDS = [
  { re: /^evidence check and limitations$/i, kind: 'check' },
  { re: /^full comparison and quoted passages\b/i, kind: 'full' },
];
const find = (rules, text) => rules.find((r) => r.re.test(norm(text))) || null;
const isHeading = (it, level) => it.type === 'heading' && (level == null || it.level === level);

/** Group the parsed line items of a v4 report into a tree, keeping every item.
 *
 *  `items` are the renderers' own first-pass items: {type:'heading'|'node', level, text,
 *  hr?}. Returns nodes of four kinds, each renderer turning them into its own markup:
 *    {t:'item', item}                          rendered as-is
 *    {t:'fold', kind, item, body}              a folded block, `item` is its heading
 *    {t:'claim', item, head, body}             one claim; `head` is what its closed row
 *                                              shows, `body` the rest
 *    {t:'cmp', item, visible, folds}           one comparison: shown lines, then folds
 *  Horizontal rules are dropped: in this layout every section already has its own frame.
 */
export function groupReport(items) {
  const out = [];
  let i = 0;
  while (i < items.length) {
    const it = items[i];
    if (it.hr) { i++; continue; }
    if (isHeading(it, 1)) {
      let k = i + 1;
      const inner = [];
      while (k < items.length && !isHeading(items[k], 1)) { inner.push(items[k]); k++; }
      if (CLAIM_HEADING.test(it.text)) out.push(groupClaim(it, inner));
      else if (find(TOP_FOLDS, it.text)) {
        out.push({ t: 'fold', kind: find(TOP_FOLDS, it.text).kind, item: it,
                   body: inner.filter((x) => !x.hr).map((x) => ({ t: 'item', item: x })) });
      } else {
        out.push({ t: 'item', item: it });
        inner.filter((x) => !x.hr).forEach((x) => out.push({ t: 'item', item: x }));
      }
      i = k;
      continue;
    }
    out.push({ t: 'item', item: it });
    i++;
  }
  return out;
}

function groupClaim(heading, inner) {
  const cut = inner.findIndex((x) => isHeading(x, 2));
  const head = (cut < 0 ? inner : inner.slice(0, cut)).filter((x) => !x.hr);
  const rest = cut < 0 ? [] : inner.slice(cut);
  const body = [];
  let j = 0;
  while (j < rest.length) {
    const it = rest[j];
    if (it.hr) { j++; continue; }
    const fold = isHeading(it, 2) ? find(CLAIM_FOLDS, it.text) : null;
    if (fold) {
      let k = j + 1;
      const b = [];
      while (k < rest.length && !(rest[k].type === 'heading' && rest[k].level <= 2)) {
        if (!rest[k].hr) b.push({ t: 'item', item: rest[k] });
        k++;
      }
      body.push({ t: 'fold', kind: fold.kind, item: it, body: b });
      j = k;
      continue;
    }
    if (isHeading(it, 3) && DETAIL_HEADING.test(it.text)) {
      let k = j + 1;
      const c = [];
      while (k < rest.length && !(rest[k].type === 'heading' && rest[k].level <= 3)) {
        c.push(rest[k]);
        k++;
      }
      body.push(groupComparison(it, c));
      j = k;
      continue;
    }
    body.push({ t: 'item', item: it });
    j++;
  }
  return { t: 'claim', item: heading, head, body };
}

function groupComparison(heading, inner) {
  const visible = [];
  const folds = [];
  let j = 0;
  while (j < inner.length && !isHeading(inner[j], 4)) {
    if (!inner[j].hr) visible.push(inner[j]);
    j++;
  }
  while (j < inner.length) {
    const it = inner[j];
    let k = j + 1;
    const b = [];
    while (k < inner.length && !(inner[k].type === 'heading' && inner[k].level <= 4)) {
      if (!inner[k].hr) b.push({ t: 'item', item: inner[k] });
      k++;
    }
    const spec = find(CMP_FOLDS, it.text);
    if (spec) folds.push({ t: 'fold', kind: spec.kind, item: it, body: b });
    else { visible.push(it); b.forEach((x) => visible.push(x.item)); } // unknown block: shown
    j = k;
  }
  return { t: 'cmp', item: heading, visible, folds };
}
