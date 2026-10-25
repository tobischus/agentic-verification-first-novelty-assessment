// Locates verified quotes in the text layer of a PDF.
const LIGATURES = { 'ﬀ': 'ff', 'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬃ': 'ffi', 'ﬄ': 'ffl', 'ﬅ': 'st' }

export const MIN_SCORE = 0.6

function expand(s) {
  return (s || '').replace(/[ﬀ-ﬅ]/g, (ch) => LIGATURES[ch] || ch)
}

export function words(text) {
  return expand(text).toLowerCase().match(/[a-z0-9]+/g) || []
}

export function pageTokens(textContent) {
  const items = textContent.items || []
  const tokens = []
  let carry = null

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
      carry = { ...tokens.pop(), to: raw.length }
    }
  })
  if (carry) tokens.push(carry)
  return tokens
}

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

  const inQuote = new Set(quoteWords)
  let { start, end } = best
  while (start <= end && !inQuote.has(tokens[start].w)) start++
  while (end >= start && !inQuote.has(tokens[end].w)) end--
  if (start > end) return null

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

let measureCtx = null
function measurer() {
  if (measureCtx === null) {
    try { measureCtx = document.createElement('canvas').getContext('2d') || false } catch { measureCtx = false }
  }
  return measureCtx
}

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

export function rectsForRange(textContent, tokens, start, end, viewportAt1, Util) {
  const spans = new Map()
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

export function locateQuotes(pages, quotes, Util) {
  const found = []
  for (const q of quotes) {
    const qw = words(q.text)
    if (qw.length < 4) continue
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
