import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { locateQuotes, pageTokens } from './locate'

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl

// Colours for quote highlights. Multiply blending keeps the glyphs underneath readable,
// which a solid fill would not, and the hues are far enough apart to tell four or five
// claims apart at a glance on a white page.
export const HIGHLIGHT_COLORS = [
  '#ffe066', '#a5d8ff', '#b2f2bb', '#ffc9c9', '#e5dbff',
  '#ffd8a8', '#99e9f2', '#fcc2d7', '#d8f5a2', '#bac8ff',
]
export const colorFor = (i) => HIGHLIGHT_COLORS[i % HIGHLIGHT_COLORS.length]

/**
 * A PDF beside the assessment, with the quoted passages marked in it.
 *
 * `highlights` is [{id, text, color, label?}]. Each is located in the text layer (see
 * locate.js) and drawn over the rendered page. `focusId` scrolls to one of them; setting
 * it again to the same id re-scrolls, so clicking the same quote twice always works.
 *
 * Pages render only once they come near the viewport. A twelve-page paper at reading
 * scale is around 40 MB of canvas if drawn all at once, which stalls the tab on the very
 * machines a reviewer is likely to use. Text extraction, by contrast, runs for every page
 * immediately: it is cheap, and a highlight cannot be found on a page nobody has read.
 */
export default function PdfViewer({ url, highlights = [], focusId = null, onLocated }) {
  const [doc, setDoc] = useState(null)
  const [pages, setPages] = useState([])       // [{viewportAt1, textContent, tokens}]
  const [scale, setScale] = useState(1.2)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const scrollRef = useRef(null)
  const pageRefs = useRef([])
  const docRef = useRef(null)     // for cleanup: destroying inside a state updater would
                                  // run twice under StrictMode

  // ------------------------------- load ---------------------------------- //
  useEffect(() => {
    if (!url) { setDoc(null); setPages([]); setError(''); return }
    let cancelled = false
    let task = null
    setLoading(true); setError(''); setDoc(null); setPages([])

    ;(async () => {
      try {
        task = pdfjsLib.getDocument({ url, isEvalSupported: false })
        const d = await task.promise
        if (cancelled) { d.destroy(); return }
        const metas = []
        for (let i = 1; i <= d.numPages; i++) {
          const page = await d.getPage(i)
          if (cancelled) return
          const textContent = await page.getTextContent()
          metas.push({
            viewportAt1: page.getViewport({ scale: 1 }),
            textContent,
            tokens: pageTokens(textContent),
          })
        }
        if (cancelled) return
        docRef.current = d
        setDoc(d)
        setPages(metas)
      } catch (e) {
        if (!cancelled) setError(String(e?.message || e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => {
      cancelled = true
      // Both: the task if the load is still in flight, the document if it finished. A
      // reviewer clicking through ten prior papers would otherwise keep all ten alive.
      try { task?.destroy() } catch { /* already gone */ }
      try { docRef.current?.destroy() } catch { /* already gone */ }
      docRef.current = null
    }
  }, [url])

  // ---------------------------- locate quotes ----------------------------- //
  // Keyed on the quote texts, not the array identity: the parent rebuilds this list on
  // every render, and re-scanning a twelve-page document on each keystroke of a claim
  // edit would make typing stutter.
  const key = useMemo(
    () => JSON.stringify(highlights.map((h) => [h.id, (h.text || '').slice(0, 400)])),
    [highlights],
  )
  const located = useMemo(() => {
    if (!pages.length || !highlights.length) return []
    return locateQuotes(pages, highlights, pdfjsLib.Util)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pages, key])

  useEffect(() => {
    if (onLocated) onLocated({ found: located.length, total: highlights.length })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [located, highlights.length])

  const byPage = useMemo(() => {
    const m = new Map()
    for (const h of located) {
      if (!m.has(h.pageIndex)) m.set(h.pageIndex, [])
      m.get(h.pageIndex).push(h)
    }
    return m
  }, [located])

  // ------------------------------- focus ---------------------------------- //
  useEffect(() => {
    if (!focusId || !located.length) return
    const target = located.find((h) => h.id === focusId)
    if (!target) return
    const el = pageRefs.current[target.pageIndex]
    if (!el || !scrollRef.current) return
    const top = target.rects.reduce((min, r) => Math.min(min, r.top), Infinity)
    // a little headroom so the passage does not sit flush against the top edge
    scrollRef.current.scrollTo({
      top: Math.max(0, el.offsetTop + top * scale - 80),
      behavior: 'smooth',
    })
  }, [focusId, located, scale])

  if (!url) return <div className="pdfpane empty">No document selected.</div>
  if (error) return <div className="pdfpane empty">Could not open this PDF — {error}</div>

  return (
    <div className="pdfpane">
      <div className="pdftools">
        <button className="link" onClick={() => setScale((s) => Math.max(0.5, +(s - 0.15).toFixed(2)))}>−</button>
        <span className="pdfzoom">{Math.round(scale * 100)}%</span>
        <button className="link" onClick={() => setScale((s) => Math.min(3, +(s + 0.15).toFixed(2)))}>+</button>
        {!!highlights.length && (
          <span className="pdfhits muted">
            {located.length}/{highlights.length} quote{highlights.length === 1 ? '' : 's'} located
          </span>
        )}
        <a className="link pdfopen" href={url} target="_blank" rel="noreferrer">open ↗</a>
      </div>
      <div className="pdfscroll" ref={scrollRef}>
        {loading && <div className="pdfloading muted">Loading document…</div>}
        {pages.map((pg, i) => (
          <PdfPage
            key={i}
            doc={doc}
            index={i}
            meta={pg}
            scale={scale}
            highlights={byPage.get(i) || []}
            pageRefs={pageRefs}
          />
        ))}
      </div>
    </div>
  )
}

/** One page: a canvas drawn on first approach, with the highlight boxes over it. */
function PdfPage({ doc, index, meta, scale, highlights, pageRefs }) {
  const holder = useRef(null)
  const canvasRef = useRef(null)
  const [visible, setVisible] = useState(index < 2)   // first pages eagerly, the rest lazily
  const renderedAt = useRef(null)

  const setRefs = useCallback((el) => {
    holder.current = el
    pageRefs.current[index] = el
  }, [pageRefs, index])

  useEffect(() => {
    const el = holder.current
    if (!el || visible) return
    const io = new IntersectionObserver(
      (entries) => { if (entries.some((e) => e.isIntersecting)) setVisible(true) },
      { rootMargin: '600px 0px' },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [visible])

  useEffect(() => {
    if (!visible || !doc || !canvasRef.current) return
    if (renderedAt.current === scale) return
    let task = null
    let cancelled = false
    ;(async () => {
      const page = await doc.getPage(index + 1)
      if (cancelled) return
      const viewport = page.getViewport({ scale })
      const canvas = canvasRef.current
      if (!canvas) return
      const ratio = window.devicePixelRatio || 1
      canvas.width = Math.floor(viewport.width * ratio)
      canvas.height = Math.floor(viewport.height * ratio)
      canvas.style.width = `${Math.floor(viewport.width)}px`
      canvas.style.height = `${Math.floor(viewport.height)}px`
      const ctx = canvas.getContext('2d')
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
      task = page.render({ canvasContext: ctx, viewport })
      try {
        await task.promise
        if (!cancelled) renderedAt.current = scale
      } catch { /* superseded by a newer render */ }
    })()
    return () => { cancelled = true; try { task?.cancel() } catch { /* not started */ } }
  }, [visible, doc, index, scale])

  const w = meta.viewportAt1.width * scale
  const h = meta.viewportAt1.height * scale

  return (
    <div className="pdfpage" ref={setRefs} style={{ width: w, height: h }}>
      <canvas ref={canvasRef} />
      {highlights.map((hl) =>
        hl.rects.map((r, k) => (
          <div
            key={hl.id + '-' + k}
            className="pdfhl"
            title={hl.label || undefined}
            style={{
              left: r.left * scale, top: r.top * scale,
              width: r.width * scale, height: r.height * scale,
              background: hl.color || HIGHLIGHT_COLORS[0],
            }}
          />
        )),
      )}
    </div>
  )
}
