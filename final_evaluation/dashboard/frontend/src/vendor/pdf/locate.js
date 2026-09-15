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
  let carry = ''            // partial word held over from a hyphenated line break
  let carryItem = -1

  items.forEach((item, idx) => {
    const raw = expand(item.str || '')
    if (!raw) return
    const hyphenated = item.hasEOL && /[-‐]$/.test(raw)
    const body = hyphenated ? raw.slice(0, -1) : raw
    const parts = body.toLowerCase().match(/[a-z0-9]+/g) || []

    parts.forEach((w, i) => {
      const first = i === 0
      if (first && carry) {
        tokens.push({ w: carry + w, item: carryItem, item2: idx })
        carry = ''
        carryItem = -1
        return
      }
      tokens.push({ w, item: idx })
    })

    if (hyphenated && parts.length) {
      // the last word of this item continues on the next line
      const last = tokens.pop()
      carry = last.w
      carryItem = last.item
    }
  })
  if (carry) tokens.push({ w: carry, item: carryItem })
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
  return { start, end, score: best.score }
}

/**
 * Rectangles covering a token range, in unscaled PDF page coordinates.
 *
 * A rectangle per text item rather than per character: pdf.js gives a width for the whole
 * item but no per-glyph advances, so any sub-item boundary would be an estimate placed
 * over real text. Whole items occasionally highlight a few words either side of the
 * quote, which is visibly approximate rather than quietly wrong.
 */
export function rectsForRange(textContent, tokens, start, end, viewportAt1, Util) {
  const used = new Set()
  for (let i = start; i <= end; i++) {
    used.add(tokens[i].item)
    if (tokens[i].item2 != null) used.add(tokens[i].item2)
  }
  const rects = []
  for (const idx of used) {
    const item = (textContent.items || [])[idx]
    if (!item || !item.transform) continue
    const tx = Util.transform(viewportAt1.transform, item.transform)
    const height = Math.hypot(tx[2], tx[3]) || item.height || 10
    const width = (item.width || 0) * (viewportAt1.scale || 1)
    if (width <= 0) continue
    rects.push({ left: tx[4], top: tx[5] - height, width, height })
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
