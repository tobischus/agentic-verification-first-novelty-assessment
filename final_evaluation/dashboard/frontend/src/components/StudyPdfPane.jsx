import { useRef, useState } from 'react'
import PdfViewer, { colorFor } from '../vendor/pdf/PdfViewer.jsx'

export default function StudyPdfPane({ url, highlights = [], focusId, onFocusChange, title }) {
  const [query, setQuery] = useState('')
  const [searchId, setSearchId] = useState(null)
  const boxRef = useRef(null)

  const doSearch = (e) => {
    e.preventDefault()
    if (!query.trim()) return
    setSearchId('search-hit')
    onFocusChange && onFocusChange('search-hit')
  }

  const toggleFullscreen = () => {
    const el = boxRef.current
    if (!el) return
    if (document.fullscreenElement) document.exitFullscreen()
    else el.requestFullscreen?.()
  }

  const effectiveHighlights = query.trim()
    ? [...highlights, { id: 'search-hit', text: query.trim(), color: colorFor(9) }]
    : highlights
  const effectiveFocus = searchId && query.trim() ? searchId : focusId

  return (
    <div className="study-pdf-pane" ref={boxRef}>
      <div className="study-pdf-bar">
        {title && <span className="study-pdf-title">{title}</span>}
        <form className="study-pdf-search" onSubmit={doSearch}>
          <input
            type="text"
            placeholder="Search in this PDF…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setSearchId(null)
            }}
          />
          <button type="submit">Find</button>
        </form>
        <button type="button" className="link" onClick={toggleFullscreen}>
          ⛶ Fullscreen
        </button>
      </div>
      <PdfViewer key={url} url={url} highlights={effectiveHighlights} focusId={effectiveFocus} />
    </div>
  )
}
