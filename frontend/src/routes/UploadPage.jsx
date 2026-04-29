import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { photoApi } from '../api.js'

const STATUS_LABELS = {
  queued: 'Queued',
  uploading: 'Uploading',
  done: 'Done',
  error: 'Failed',
}

export default function UploadPage() {
  const [items, setItems] = useState([])      // [{ id, file, status, progress, error }]
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const inputRef = useRef(null)
  const navigate = useNavigate()

  const addFiles = (list) => {
    const incoming = Array.from(list || [])
      .filter((f) => f.type.startsWith('image/'))
      .map((file) => ({
        id: `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2)}`,
        file,
        status: 'queued',
        progress: 0,
        error: null,
      }))
    setItems((prev) => [...prev, ...incoming])
  }

  const removeItem = (id) => setItems((prev) => prev.filter((i) => i.id !== id))
  const clearAll = () => setItems([])

  const onDrop = (e) => {
    e.preventDefault(); setDragging(false)
    addFiles(e.dataTransfer.files)
  }

  const updateItem = (id, patch) => {
    setItems((prev) => prev.map((i) => (i.id === id ? { ...i, ...patch } : i)))
  }

  const uploadOne = async (item) => {
    updateItem(item.id, { status: 'uploading', progress: 0 })
    try {
      await photoApi.uploadWithProgress(item.file, (p) => {
        updateItem(item.id, { progress: p })
      })
      updateItem(item.id, { status: 'done', progress: 100 })
    } catch (err) {
      updateItem(item.id, {
        status: 'error',
        error: err.response?.data?.message || 'Upload failed',
      })
    }
  }

  const onSubmit = async (e) => {
    e.preventDefault()
    if (items.length === 0 || busy) return
    setBusy(true)
    // Параллелим, но не больше 3 одновременных upload'ов чтобы не задушить ML очередь
    const queue = items.filter((i) => i.status === 'queued' || i.status === 'error')
    const concurrency = 3
    let cursor = 0
    const workers = Array.from({ length: concurrency }, async () => {
      while (cursor < queue.length) {
        const idx = cursor++
        await uploadOne(queue[idx])
      }
    })
    await Promise.all(workers)
    setBusy(false)
    // Если все ушли успешно — переход в галерею
    setItems((prev) => {
      const allDone = prev.length > 0 && prev.every((i) => i.status === 'done')
      if (allDone) setTimeout(() => navigate('/'), 600)
      return prev
    })
  }

  const totalDone = items.filter((i) => i.status === 'done').length
  const totalError = items.filter((i) => i.status === 'error').length

  return (
    <div className="upload-page">
      <div className="upload-card">
        <h1>Upload</h1>
        <form onSubmit={onSubmit}>
          <div
            className={`dropzone ${dragging ? 'dragging' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
          >
            <div className="big">Drop images or click to browse</div>
            <div className="small">JPEG · PNG · WebP — up to 25 MB each · multiple OK</div>
            <input
              ref={inputRef}
              type="file"
              accept="image/*"
              multiple
              style={{ display: 'none' }}
              onChange={(e) => { addFiles(e.target.files); e.target.value = '' }}
            />
          </div>

          {items.length > 0 && (
            <div className="upload-list">
              {items.map((i) => (
                <div key={i.id} className={`upload-row ${i.status}`}>
                  <div className="upload-row-name" title={i.file.name}>{i.file.name}</div>
                  <div className="upload-row-size">{(i.file.size / 1024).toFixed(0)} KB</div>
                  <div className="upload-row-bar">
                    <div
                      className="upload-row-fill"
                      style={{ width: `${i.status === 'done' ? 100 : i.progress}%` }}
                    />
                  </div>
                  <div className="upload-row-status">
                    {i.status === 'error'
                      ? <span title={i.error}>{STATUS_LABELS.error}</span>
                      : STATUS_LABELS[i.status]}
                  </div>
                  {!busy && i.status !== 'done' && (
                    <button
                      type="button"
                      className="upload-row-remove"
                      onClick={() => removeItem(i.id)}
                      aria-label="Remove"
                    >×</button>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="upload-actions" style={{ marginTop: 18 }}>
            <button type="submit" className="btn" disabled={items.length === 0 || busy}>
              {busy
                ? `Uploading ${totalDone}/${items.length}…`
                : items.length > 1
                  ? `Analyze ${items.length} photos`
                  : 'Analyze'}
            </button>
            {items.length > 0 && !busy && (
              <button type="button" className="btn secondary" onClick={clearAll}>
                Clear all
              </button>
            )}
            {totalError > 0 && !busy && (
              <span className="form-error">{totalError} failed</span>
            )}
          </div>
        </form>
      </div>
    </div>
  )
}
