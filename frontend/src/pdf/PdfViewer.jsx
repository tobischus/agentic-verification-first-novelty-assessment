import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { locateQuotes, pageTokens } from './locate'

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl

export const HIGHLIGHT_COLORS = [
  '#ffe066',
  '#a5d8ff',
  '#b2f2bb',
  '#ffc9c9',
  '#e5dbff',
  '#ffd8a8',
  '#99e9f2',
  '#fcc2d7',
  '#d8f5a2',
  '#bac8ff',
]
export const colorFor = (i) => HIGHLIGHT_COLORS[i % HIGHLIGHT_COLORS.length]

export default function PdfViewer({ url, highlights = [], focusId = null, onLocated }) {
  const [doc, setDoc] = useState(null)
  const [pages, setPages] = useState([])
  const [scale, setScale] = useState(1.2)
  const userZoomed = useRef(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const scrollRef = useRef(null)
  const paneRef = useRef(null)
  const pageRefs = useRef([])
  const docRef = useRef(null)

  useEffect(() => {
    if (!url) {
      setDoc(null)
      setPages([])
      setError('')
      return
    }
    let cancelled = false
    let task = null
    setLoading(true)
    setError('')
    setDoc(null)
    setPages([])
    ;(async () => {
      try {
        task = pdfjsLib.getDocument({ url, isEvalSupported: false })
        const d = await task.promise
        if (cancelled) {
          d.destroy()
          return
        }
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
      try {
        task?.destroy()
      } catch {}
      try {
        docRef.current?.destroy()
      } catch {}
      docRef.current = null
    }
  }, [url])

  const key = useMemo(
    () => JSON.stringify(highlights.map((h) => [h.id, (h.text || '').slice(0, 400)])),
    [highlights],
  )
  const located = useMemo(() => {
    if (!pages.length || !highlights.length) return []
    return locateQuotes(pages, highlights, pdfjsLib.Util)
  }, [pages, key])

  useEffect(() => {
    if (onLocated) onLocated({ found: located.length, total: highlights.length })
  }, [located, highlights.length])

  useEffect(() => {
    const pane = paneRef.current
    if (!pages.length || !pane) return
    const fit = () => {
      if (userZoomed.current) return
      const avail = pane.clientWidth - 26
      const w = pages[0].viewportAt1.width
      if (avail > 100 && w > 0) {
        setScale(Math.min(2.5, Math.max(0.4, Math.round((avail / w) * 100) / 100)))
      }
    }
    fit()
    const ro = new ResizeObserver(fit)
    ro.observe(pane)
    return () => ro.disconnect()
  }, [pages])

  const zoom = (d) => {
    userZoomed.current = true
    setScale((sc) => Math.min(3, Math.max(0.4, +(sc + d).toFixed(2))))
  }

  const colorKey = highlights.map((h) => `${h.id}:${h.color || ''}`).join('|')
  const byPage = useMemo(() => {
    const colorOf = new Map(highlights.map((h) => [h.id, h.color]))
    const m = new Map()
    const ordered = [...located].sort((a, b) => (b.id === focusId) - (a.id === focusId))
    for (const h of ordered) {
      if (!m.has(h.pageIndex)) m.set(h.pageIndex, [])
      m.get(h.pageIndex).push({ ...h, color: colorOf.get(h.id) ?? h.color })
    }
    return m
  }, [located, colorKey, focusId])

  useEffect(() => {
    if (!focusId || !located.length) return
    const target = located.find((h) => h.id === focusId)
    if (!target) return
    const el = pageRefs.current[target.pageIndex]
    const box = scrollRef.current
    if (!el || !box) return
    const first = target.rects.reduce((min, r) => Math.min(min, r.top), Infinity)
    const delta = el.getBoundingClientRect().top - box.getBoundingClientRect().top
    const top = Math.max(0, box.scrollTop + delta + first * scale - 90)
    const far = Math.abs(top - box.scrollTop) > box.clientHeight * 3
    box.scrollTo({ top, behavior: far ? 'auto' : 'smooth' })
  }, [focusId, located, scale])

  if (!url) return <div className="pdfpane empty">No document selected.</div>
  if (error) return <div className="pdfpane empty">Could not open this PDF — {error}</div>

  return (
    <div className="pdfpane" ref={paneRef}>
      <div className="pdftools">
        <button className="link" onClick={() => zoom(-0.15)}>
          −
        </button>
        <span className="pdfzoom">{Math.round(scale * 100)}%</span>
        <button className="link" onClick={() => zoom(0.15)}>
          +
        </button>
        {!!highlights.length && (
          <span className="pdfhits muted">
            {located.length}/{highlights.length} quote{highlights.length === 1 ? '' : 's'} located
          </span>
        )}
        <a className="link pdfopen" href={url} target="_blank" rel="noreferrer">
          Open in new tab
        </a>
      </div>
      <div className="pdfscroll" ref={scrollRef}>
        {loading && <div className="pdfloading muted">Loading document…</div>}
        <div className="pdfpages">
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
    </div>
  )
}

function PdfPage({ doc, index, meta, scale, highlights, pageRefs }) {
  const holder = useRef(null)
  const canvasRef = useRef(null)
  const [visible, setVisible] = useState(index < 2)
  const renderedAt = useRef(null)

  const setRefs = useCallback(
    (el) => {
      holder.current = el
      pageRefs.current[index] = el
    },
    [pageRefs, index],
  )

  useEffect(() => {
    const el = holder.current
    if (!el || visible) return
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) setVisible(true)
      },
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
      } catch {}
    })()
    return () => {
      cancelled = true
      try {
        task?.cancel()
      } catch {}
    }
  }, [visible, doc, index, scale])

  const w = meta.viewportAt1.width * scale
  const h = meta.viewportAt1.height * scale

  const boxes = useMemo(() => {
    const byRect = new Map()
    for (const hl of highlights) {
      for (const r of hl.rects) {
        const key = [r.top, r.left, r.width, r.height].map((v) => v.toFixed(1)).join(',')
        let box = byRect.get(key)
        if (!box) {
          box = { rect: r, color: hl.color, ids: [], labels: [] }
          byRect.set(key, box)
        }
        box.ids.push(hl.id)
        if (hl.label) box.labels.push(hl.label)
      }
    }
    return [...byRect.values()]
  }, [highlights])

  return (
    <div className="pdfpage" ref={setRefs} style={{ width: w, height: h }}>
      <canvas ref={canvasRef} />
      {boxes.map((box, k) => (
        <div
          key={box.ids[0] + '-' + k}
          className="pdfhl"
          title={box.labels.length ? box.labels.join(' · ') : undefined}
          style={{
            left: box.rect.left * scale,
            top: box.rect.top * scale,
            width: box.rect.width * scale,
            height: box.rect.height * scale,
            background: box.color || HIGHLIGHT_COLORS[0],
          }}
        />
      ))}
    </div>
  )
}
