import { useEffect, useState } from 'react'
import { photoApi } from '../api.js'

export default function PhotoModal({ photo, onClose, onOpenPhoto }) {
  const [similar, setSimilar] = useState([])
  const [similarLoading, setSimilarLoading] = useState(false)

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    if (!photo) return
    const topStyle = photo.styles?.[0]?.name
    if (!topStyle) { setSimilar([]); return }
    setSimilarLoading(true)
    photoApi.search(topStyle, 0.1, 0, 12)
      .then(({ data }) => {
        const items = (data.content || []).filter((p) => p.id !== photo.id).slice(0, 6)
        setSimilar(items)
      })
      .catch(() => setSimilar([]))
      .finally(() => setSimilarLoading(false))
  }, [photo])

  if (!photo) return null

  const onBackdrop = (e) => {
    if (e.target === e.currentTarget) onClose()
  }

  const styles = photo.styles || []
  const isPending = photo.status !== 'DONE'

  return (
    <div className="modal-backdrop" onClick={onBackdrop}>
      <div className="modal">
        <div className="modal-image">
          <button className="modal-close" onClick={onClose} aria-label="Close">✕</button>
          {photo.url && <img src={photo.url} alt="" />}
        </div>
        <div className="modal-panel">
          <div>
            <div className="panel-label">Visual style analysis</div>
            <div className="analysis" style={{ marginTop: 12 }}>
              {isPending && styles.length === 0 ? (
                <div className="similar-empty">Analysis in progress…</div>
              ) : styles.length === 0 ? (
                <div className="similar-empty">No styles detected</div>
              ) : (
                styles.map((s) => (
                  <div className="style-row" key={s.name}>
                    <span className="name">{s.name}</span>
                    <span className="bar">
                      <span className="fill" style={{ width: `${Math.round(s.confidence * 100)}%` }} />
                    </span>
                    <span className="pct">{Math.round(s.confidence * 100)}%</span>
                  </div>
                ))
              )}
            </div>
          </div>

          <div>
            <div className="panel-label">Similar photos</div>
            <div style={{ marginTop: 12 }}>
              {similarLoading ? (
                <div className="similar-empty">Loading…</div>
              ) : similar.length === 0 ? (
                <div className="similar-empty">No similar photos</div>
              ) : (
                <div className="similar-grid">
                  {similar.map((p) => {
                    const top = p.styles?.[0]
                    return (
                      <div
                        key={p.id}
                        className="similar-cell"
                        onClick={() => onOpenPhoto?.(p)}
                      >
                        {p.url && <img src={p.url} alt="" loading="lazy" />}
                        {top && (
                          <div className="hover-tag">
                            <span className="tag">{top.name}</span>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
