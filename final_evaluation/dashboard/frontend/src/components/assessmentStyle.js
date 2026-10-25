// Colours for the report's assessment wording and resolution of its jump links. Identical copy in the main frontend.
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

const alt = (map) =>
  Object.keys(map)
    .sort((a, b) => b.length - a.length)
    .map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('|');

const DEGREE_RE = new RegExp(`^(${alt(DEGREES)})(?:\\s*·\\s*(${alt(EVIDENCE)}))?`, 'i');
const VERDICT_RE = new RegExp(`^(${alt(VERDICTS)})`, 'i');
const EVIDENCE_RE = new RegExp(`^(${alt(EVIDENCE)})`, 'i');

export const ASSESSMENT_LINE = /^\*\*(Assessment|Status):\*\*\s*(.+)$/;

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

export const CLAIM_HEADING = /^Claim\s+(\d+)\s+[—-]\s+Review$/;
export const DETAIL_HEADING = /^(R\d+)\s+[—-]\s+/;
const ANCHOR_HREF = /^#(cmp-\d+-R\d+)$/;

export const anchorId = (idPrefix, claimNo, ref) => `${idPrefix}-cmp-${claimNo}-${ref}`;

export const resolveAnchor = (idPrefix, href) => {
  const m = ANCHOR_HREF.exec(href || '');
  return m ? `${idPrefix}-${m[1]}` : null;
};

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
    const id = sub.get(norm(t.slice(2)).replace(/^[“"]/, '').replace(/[”"]$/, ''));
    if (id && !out.has(id)) out.set(id, claimNo);
  }
  return out;
}

export function jumpToId(id) {
  const el = typeof document === 'undefined' ? null : document.getElementById(id);
  if (!el) return false;
  for (let n = el; n; n = n.parentElement) if (n.tagName === 'DETAILS') n.open = true;
  el.scrollIntoView({ block: 'start', behavior: 'smooth' });
  el.classList.add('as-flash');
  setTimeout(() => el.classList.remove('as-flash'), 1500);
  return true;
}

export const SUB_BLOCKS = [
  { re: /^prior work summary$/i, kind: 'priorwork', open: false },
  { re: /^comparison$/i, kind: 'comparison', open: true },
  { re: /^evidence pairs$/i, kind: 'pairs', open: true },
  { re: /^pairs not used to support overlap\b/i, kind: 'unused', open: false },
  { re: /^evidence-check assessment$/i, kind: 'check', open: false },
];

export const subBlock = (text) => SUB_BLOCKS.find((s) => s.re.test(norm(text))) || null;

export const isGroupedLayout = (text) =>
  /^# (Metadata|How to read the assessments)\s*$/m.test(text || '');

export const VERDICT_LINE = /^\*\*Verdict:\*\*\s*(.+)$/;
export const OPEN_POINT_LINE = /^\*\*Open points?:\*\*\s*(.+)$/;

const TOP_FOLDS = [
  { re: /^how to read the assessments$/i, kind: 'legend' },
  { re: /^related work examined$/i, kind: 'matrix' },
  { re: /^metadata$/i, kind: 'meta' },
];
const CLAIM_FOLDS = [
  { re: /^submission passages$/i, kind: 'passages' },
  { re: /^coverage and limitations$/i, kind: 'coverage' },
];
const CMP_FOLDS = [
  { re: /^evidence check and limitations$/i, kind: 'check' },
  { re: /^full comparison and quoted passages\b/i, kind: 'full' },
];
const find = (rules, text) => rules.find((r) => r.re.test(norm(text))) || null;
const isHeading = (it, level) => it.type === 'heading' && (level == null || it.level === level);

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
    else { visible.push(it); b.forEach((x) => visible.push(x.item)); }
    j = k;
  }
  return { t: 'cmp', item: heading, visible, folds };
}
