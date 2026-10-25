import { useCallback, useEffect, useRef, useState } from 'react'

export default function SplitView({ left, right, storageKey = 'split', minLeft = 320, minRight = 320 }) {
  const [pct, setPct] = useState(() => {
    const v = Number(localStorage.getItem(`split:${storageKey}`))
    return v >= 20 && v <= 80 ? v : 50
  })
  const [dragging, setDragging] = useState(false)
  const box = useRef(null)

  const onMove = useCallback((clientX) => {
    const el = box.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const x = Math.min(Math.max(clientX - r.left, minLeft), r.width - minRight)
    if (r.width - minRight < minLeft) return
    setPct(Math.round((x / r.width) * 1000) / 10)
  }, [minLeft, minRight])

  useEffect(() => {
    if (!dragging) return
    const move = (e) => { e.preventDefault(); onMove(e.touches ? e.touches[0].clientX : e.clientX) }
    const up = () => setDragging(false)
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
    window.addEventListener('touchmove', move, { passive: false })
    window.addEventListener('touchend', up)
    return () => {
      window.removeEventListener('mousemove', move)
      window.removeEventListener('mouseup', up)
      window.removeEventListener('touchmove', move)
      window.removeEventListener('touchend', up)
    }
  }, [dragging, onMove])

  useEffect(() => { localStorage.setItem(`split:${storageKey}`, String(pct)) }, [pct, storageKey])

  if (!right) return <>{left}</>

  return (
    <div className={'splitview' + (dragging ? ' dragging' : '')} ref={box}>
      <div className="split-left" style={{ width: `${pct}%` }}>{left}</div>
      <div
        className="split-handle"
        onMouseDown={() => setDragging(true)}
        onTouchStart={() => setDragging(true)}
        onDoubleClick={() => setPct(50)}
        role="separator"
        aria-orientation="vertical"
        title="Drag to resize · double-click to even out"
      />
      <div className="split-right" style={{ width: `calc(${100 - pct}% - 10px)` }}>{right}</div>
    </div>
  )
}
