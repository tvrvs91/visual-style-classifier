import { useCallback, useEffect, useRef, useState } from 'react'
import { photoApi, styleApi } from '../api.js'
import PhotoCell, { cellClass } from '../components/PhotoCell.jsx'
import PhotoModal from '../components/PhotoModal.jsx'
import { useToast } from '../ToastContext.jsx'

export default function GalleryPage() {
  const toast = useToast()
  const [photos, setPhotos] = useState([])
  const [styles, setStyles] = useState([])
  const [filterStyle, setFilterStyle] = useState('')
  const [minConfidence, setMinConfidence] = useState(0.2)
  const [loading, setLoading] = useState(false)
  const [active, setActive] = useState(null)
  const pollRef = useRef(null)

  const handleDelete = useCallback(async (photo) => {
    try {
      await photoApi.delete(photo.id)
      setPhotos((prev) => prev.filter((p) => p.id !== photo.id))
      setActive((curr) => (curr?.id === photo.id ? null : curr))
      toast.success('Photo deleted')
    } catch (err) {
      toast.error(err.response?.data?.message || 'Delete failed')
    }
  }, [toast])

  useEffect(() => {
    styleApi.list()
      .then(({ data }) => setStyles(data))
      .catch(() => setStyles([]))
  }, [])

  const fetchPhotos = useCallback(async () => {
    try {
      const { data } = filterStyle
        ? await photoApi.search(filterStyle, minConfidence, 0, 60)
        : await photoApi.list(0, 60)
      setPhotos(data.content || [])
    } catch { /* 401 handled by axios interceptor */ }
  }, [filterStyle, minConfidence])

  useEffect(() => {
    setLoading(true)
    fetchPhotos().finally(() => setLoading(false))
  }, [fetchPhotos])

  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current)
    const hasPending = photos.some((p) => p.status === 'PENDING')
    if (hasPending) pollRef.current = setInterval(fetchPhotos, 3000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [photos, fetchPhotos])

  useEffect(() => {
    if (!active) return
    const fresh = photos.find((p) => p.id === active.id)
    if (fresh && fresh !== active) setActive(fresh)
  }, [photos, active])

  return (
    <>
      <div className="filter-bar">
        <button
          className={`filter-pill ${filterStyle === '' ? 'active' : ''}`}
          onClick={() => setFilterStyle('')}
        >
          All
        </button>
        {styles.map((s) => (
          <button
            key={s}
            className={`filter-pill ${filterStyle === s ? 'active' : ''}`}
            onClick={() => setFilterStyle(s)}
          >
            {s.replace('_', ' ')}
          </button>
        ))}
        <span className="spacer" />
        {filterStyle && (
          <span className="conf">
            Min&nbsp;
            <input
              type="number" step="0.05" min="0" max="1"
              value={minConfidence}
              onChange={(e) => setMinConfidence(Number(e.target.value))}
            />
          </span>
        )}
      </div>

      <div className="gallery">
        {loading ? (
          <div className="gallery-grid">
            {Array.from({ length: 18 }).map((_, i) => (
              <div key={i} className={`cell skeleton ${cellClass(i)}`} />
            ))}
          </div>
        ) : photos.length === 0 ? (
          <div className="empty">No photos yet</div>
        ) : (
          <div className="gallery-grid">
            {photos.map((p, i) => (
              <PhotoCell
                key={p.id}
                photo={p}
                index={i}
                onClick={setActive}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </div>

      {active && (
        <PhotoModal
          photo={active}
          onClose={() => setActive(null)}
          onOpenPhoto={setActive}
          onDelete={handleDelete}
        />
      )}
    </>
  )
}
