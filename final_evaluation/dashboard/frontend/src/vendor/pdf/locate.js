// Finding a quote inside a PDF's text layer.
//
// The quotes this system shows were verified against GROBID's extraction of the paper,
// not against pdf.js's. The two disagree in small ways on every document: ligatures,
// hyphenation at line breaks, the order of a running head, whether a superscript sits
// inside a word. An exact string search therefore fails on perfectly good quotes, which
// would tell the reviewer the quote is not in the paper -- the one thing this view must
// never do.
//
// So matching is on word tokens, not characters, and scored rather than boolean: strip
// everything but letters and digits, then slide a window the length of the quote across
// the page and keep the best-overlapping one. Below MIN_SCORE nothing is reported, on the
// principle that showing no highlight is honest while showing a wrong one is not.

// Ligatures pdf.js hands back as single code points; GROBID usually splits them.
const LIGATURES = { 'ﬀ': 'ff', 'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬃ': 'ffi', 'ﬄ': 'ffl', 'ﬅ': 'st' }

// Below this share of the quote's words found in order-free overlap, report nothing.
export const MIN_SCORE = 0.6

function expand(s) {
  return (s || '').replace(/[ﬀ-ﬅ]/g, (ch) => LIGATURES[ch] || ch)
}

/** Words of a string, lowercased, punctuation dropped. The unit both sides are compared in. */
export function words(text) {
  return expand(text).toLowerCase().match(/[a-z0-9]+/g) || []
}

/**
 * One page's text as a token list carrying, for each token, the text item it came from.
 *
 * Items are joined with a space, except where an item ends in a hyphen AND pdf.js marks a
 * line end there -- that is real line-break hyphenation ("trans-\nducer"), and joining
 * without the hyphen restores the word. A hyphen inside a line is left alone: it is part
 * of a compound, and both extractions then split it the same way.
 */
export function pageTokens(textContent) {
  const items = textContent.items || []
  const tokens = []
  let carry = null          // partial word held over from a hyphenated line break

  // Each token also records where it sits inside its item's (ligature-expanded) string,
  // `from`/`to`, so a highlight can start and end inside a line rather than cover it whole.
  // A word joined across a hyphenated break keeps both halves: item/from/to on the first
  // line (hyphen included), item2/from2/to2 on the second.
  items.forEach((item, idx) => {
    const raw = expand(item.str || '')
    if (!raw) return
    const hyphenated = item.hasEOL && /[-‐]$/.test(raw)
    const body = hyphenated ? raw.slice(0, -1) : raw
    const parts = [...body.toLowerCase().matchAll(/[a-z0-9]+/g)]

    parts.forEach((m, i) => {
      const w = m[0]
      const from = m.index
      const to = m.index + w.length
      if (i === 0 && carry) {
        tokens.push({ ...carry, w: carry.w + w, item2: idx, from2: from, to2: to })
        carry = null
        return
      }
      tokens.push({ w, item: idx, from, to })
    })

    if (hyphenated && parts.length) {
      // the last word of this item continues on the next line
      carry = { ...tokens.pop(), to: raw.length }
    }
  })
  if (carry) tokens.push(carry)
  return tokens
}

/**
 * Best window of `tokens` matching `quote`, or null.
 *
 * Scoring is multiset overlap inside a sliding window, maintained incrementally, so the
 * cost is linear in the page rather than quadratic. Order is deliberately ignored: the
 * failure modes above reorder and split words, and demanding the exact sequence rejects
 * matches a reader would call obviously correct. Ordering is not needed to disambiguate
 * either -- a 20-word window matching 60% of a specific quote occurs once in a paper.
 *
 * Returns {start, end, score} as inclusive token indices.
 */
export function findWindow(tokens, quoteWords) {
  const m = quoteWords.length
  if (!m || tokens.length < 1) return null

  const need = new Map()
  for (const w of quoteWords) need.set(w, (need.get(w) || 0) + 1)

  const have = new Map()
  let matched = 0
  let best = null
  const width = Math.min(m, tokens.length)

  const add = (w) => {
    if (!need.has(w)) return
    const h = (have.get(w) || 0) + 1
    have.set(w, h)
    if (h <= need.get(w)) matched++
  }
  const drop = (w) => {
    if (!need.has(w)) return
    const h = have.get(w) - 1
    have.set(w, h)
    if (h < need.get(w)) matched--
  }

  for (let i = 0; i < tokens.length; i++) {
    add(tokens[i].w)
    if (i >= width) drop(tokens[i - width].w)
    if (i >= width - 1) {
      const score = matched / m
      if (!best || score > best.score) best = { start: i - width + 1, end: i, score }
    }
  }
  if (!best || best.score < MIN_SCORE) return null

  // Trim the window to the first and last token that actually belongs to the quote, so a
  // match near a page edge does not drag in a heading or a footnote beside it.
  const inQuote = new Set(quoteWords)
  let { start, end } = best
  while (start <= end && !inQuote.has(tokens[start].w)) start++
  while (end >= start && !inQuote.has(tokens[end].w)) end--
  if (start > end) return null

  // Order-free scoring lets the window begin a few words early on words the quote also
  // uses further on -- "... based on its position in context. In this work, ..." for a
  // quote that starts "In this work" and later says "in context" -- and, being exactly
  // as wide as the quote, then end the same few words short. Where the page has the
  // quote's own first (last) three words in sequence close by, the range snaps to them.
  // Where it does not (the extractions disagree there), the trimmed window stands.
  const K = 3
  if (m > K) {
    const slack = Math.max(8, Math.ceil(m * 0.4))
    const seqAt = (i, ws) => i >= 0 && ws.every((w, k) => tokens[i + k] && tokens[i + k].w === w)
    const nearest = (from, ok) => {
      for (let d = 0; d <= slack; d++) {
        if (ok(from + d)) return from + d
        if (d && ok(from - d)) return from - d
      }
      return null
    }
    const head = quoteWords.slice(0, K)
    const tail = quoteWords.slice(-K)
    const s = nearest(start, (i) => seqAt(i, head))
    const e = nearest(end, (j) => seqAt(j - K + 1, tail))
    if (s != null) start = s
    if (e != null && e >= start) end = e
  }
  return { start, end, score: best.score }
}

// A 2D context for measuring text, made once; false where there is none (no DOM).
let measureCtx = null
function measurer() {
  if (measureCtx === null) {
    try { measureCtx = document.createElement('canvas').getContext('2d') || false } catch { measureCtx = false }
  }
  return measureCtx
}

/** How far into `str` character `i` starts, as a share of the whole string's width. */
function widthShare(str, i, fontFamily) {
  if (i <= 0) return 0
  if (i >= str.length) return 1
  const c = measurer()
  if (c) {
    c.font = `100px ${fontFamily || 'serif'}`
    const whole = c.measureText(str).width
    if (whole > 0) return c.measureText(str.slice(0, i)).width / whole
  }
  return i / str.length
}

/**
 * Rectangles covering a token range, in unscaled PDF page coordinates.
 *
 * pdf.js gives each text item (often a whole line) a width but no per-glyph advances.
 * An item the quote covers completely gets its full rectangle. An item it covers only in
 * part -- the line a quote starts or ends in the middle of -- is cut at the quote's first
 * or last character, placed by that character's share of the item's width as measured in
 * the item's generic font family. That is an estimate of a few points at most; a whole
 * line, which this used to draw, marked words outside the quote as quoted.
 */
export function rectsForRange(textContent, tokens, start, end, viewportAt1, Util) {
  const spans = new Map()      // item index -> [from, to) the quote covers in it
  const cover = (idx, from, to) => {
    if (idx == null || idx < 0) return
    const s = spans.get(idx)
    spans.set(idx, s ? [Math.min(s[0], from), Math.max(s[1], to)] : [from, to])
  }
  for (let i = start; i <= end; i++) {
    const t = tokens[i]
    cover(t.item, t.from ?? 0, t.to ?? Infinity)
    if (t.item2 != null) cover(t.item2, t.from2 ?? 0, t.to2 ?? Infinity)
  }
  const rects = []
  for (const [idx, [from, rawTo]] of spans) {
    const item = (textContent.items || [])[idx]
    if (!item || !item.transform) continue
    const tx = Util.transform(viewportAt1.transform, item.transform)
    const height = Math.hypot(tx[2], tx[3]) || item.height || 10
    const width = (item.width || 0) * (viewportAt1.scale || 1)
    if (width <= 0) continue
    const str = expand(item.str || '')
    // A closing mark right after the last word belongs to the quote's visual end.
    let to = Math.min(rawTo, str.length)
    while (to < str.length && /[.,;:!?)\]”’"']/.test(str[to])) to++
    const family = textContent.styles?.[item.fontName]?.fontFamily
    const a = widthShare(str, from, family)
    const b = widthShare(str, to, family)
    if (b <= a) continue
    rects.push({ left: tx[4] + width * a, top: tx[5] - height, width: width * (b - a), height })
  }
  return mergeRows(rects)
}

/** Merge rectangles that sit on the same line into one, so a quote reads as a band. */
function mergeRows(rects) {
  const sorted = [...rects].sort((a, b) => a.top - b.top || a.left - b.left)
  const out = []
  for (const r of sorted) {
    const prev = out[out.length - 1]
    const sameRow = prev && Math.abs(prev.top - r.top) < Math.min(prev.height, r.height) * 0.6
    const adjacent = prev && r.left <= prev.left + prev.width + r.height * 1.2
    if (sameRow && adjacent) {
      const right = Math.max(prev.left + prev.width, r.left + r.width)
      prev.left = Math.min(prev.left, r.left)
      prev.width = right - prev.left
      prev.top = Math.min(prev.top, r.top)
      prev.height = Math.max(prev.height, r.height)
    } else {
      out.push({ ...r })
    }
  }
  return out
}

/**
 * Locate every quote across every page.
 *
 * `pages` is [{textContent, tokens, viewportAt1}], `quotes` is [{id, text, color}].
 * A quote is reported on its single best page: a passage quoted once should light up
 * once, and the running head that repeats a title on every page should not.
 */
export function locateQuotes(pages, quotes, Util) {
  const found = []
  for (const q of quotes) {
    const qw = words(q.text)
    if (qw.length < 4) continue          // too short to identify a passage
    let best = null
    pages.forEach((pg, pageIndex) => {
      const hit = findWindow(pg.tokens, qw)
      if (hit && (!best || hit.score > best.hit.score)) best = { pageIndex, hit }
    })
    if (!best) continue
    const pg = pages[best.pageIndex]
    const rects = rectsForRange(pg.textContent, pg.tokens, best.hit.start, best.hit.end,
                                pg.viewportAt1, Util)
    if (rects.length) {
      found.push({ ...q, pageIndex: best.pageIndex, score: best.hit.score, rects })
    }
  }
  return found
}
