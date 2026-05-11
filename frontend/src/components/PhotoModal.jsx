import { useEffect, useState } from 'react'
import { photoApi } from '../api.js'

const SCORE_LABELS = {
  brightness: 'Brightness',
  contrast: 'Contrast',
  saturation: 'Saturation',
  warmth: 'Warmth',
  sharpness: 'Sharpness',
}
const SCORE_ORDER = ['brightness', 'contrast', 'saturation', 'warmth', 'sharpness']

export default function PhotoModal({ photo, onClose, onOpenPhoto, onDelete }) {
  const [similar, setSimilar] = useState([])
  const [similarLoading, setSimilarLoading] = useState(false)

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    if (!photo) return
    setSimilarLoading(true)
    // Embedding-based similarity (cosine sim в 1280-dim пространстве признаков EfficientNet)
    photoApi.similar(photo.id, 6)
      .then(({ data }) => setSimilar(data || []))
      .catch(() => setSimilar([]))
      .finally(() => setSimilarLoading(false))
  }, [photo])

  if (!photo) return null

  const onBackdrop = (e) => {
    if (e.target === e.currentTarget) onClose()
  }

  const styles = photo.styles || []
  const palette = photo.palette || []
  const scores = photo.scores || {}
  const isPending = photo.status !== 'DONE'

  return (
    <div className="modal-backdrop" onClick={onBackdrop}>
      <div className="modal">
        <div className="modal-image">
          <button className="modal-close" onClick={onClose} aria-label="Close">✕</button>
          {onDelete && (
            <button
              className="modal-delete"
              onClick={() => {
                if (window.confirm('Delete this photo?')) onDelete(photo)
              }}
            >
              Delete
            </button>
          )}
          {photo.url && <img src={photo.url} alt="" />}
        </div>

        <div className="modal-panel">
          {/* 1. Style analysis */}
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

          {/* 2. Color palette */}
          {palette.length > 0 && (
            <div>
              <div className="panel-label">Color palette</div>
              <div className="palette-row" style={{ marginTop: 12 }}>
                {palette.map((hex, i) => (
                  <div
                    key={`${hex}-${i}`}
                    className="palette-swatch"
                    title={hex}
                    style={{ backgroundColor: hex }}
                  >
                    <span className="palette-hex">{hex}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 3. Score card — количественные атрибуты */}
          {Object.keys(scores).length > 0 && (
            <div>
              <div className="panel-label">Image attributes</div>
              <div className="analysis" style={{ marginTop: 12 }}>
                {SCORE_ORDER.filter((k) => k in scores).map((k) => {
                  const v = scores[k]
                  return (
                    <div className="style-row" key={k}>
                      <span className="name">{SCORE_LABELS[k]}</span>
                      <span className="bar">
                        <span
                          className="fill"
                          style={{
                            width: `${Math.round(v * 100)}%`,
                            background: 'var(--text-dim)',
                          }}
                        />
                      </span>
                      <span className="pct">{Math.round(v * 100)}%</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* 4. Similar photos (embedding cosine sim) */}
          <div>
            <div className="panel-label">Similar photos</div>
            <div style={{ marginTop: 12 }}>
              {similarLoading ? (
                <div className="similar-empty">Loading…</div>
              ) : similar.length === 0 ? (
                <div className="similar-empty">No similar photos yet</div>
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
