import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { photoApi } from '../api.js'

export default function UploadPage() {
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const onDrop = (e) => {
    e.preventDefault(); setDragging(false)
    const f = e.dataTransfer.files?.[0]
    if (f) setFile(f)
  }

  const onSubmit = async (e) => {
    e.preventDefault()
    if (!file) return
    setError(''); setLoading(true)
    try {
      await photoApi.upload(file)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.message || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

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
            onClick={() => document.getElementById('file-input').click()}
          >
            {file ? (
              <>
                <div className="big">{file.name}</div>
                <div className="small">{(file.size / 1024).toFixed(1)} KB</div>
              </>
            ) : (
              <>
                <div className="big">Drop image or click to browse</div>
                <div className="small">JPEG · PNG · WebP — up to 25 MB</div>
              </>
            )}
            <input id="file-input" type="file" accept="image/*" style={{ display: 'none' }}
                   onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </div>

          <div className="upload-actions" style={{ marginTop: 18 }}>
            <button type="submit" className="btn" disabled={!file || loading}>
              {loading ? 'Uploading…' : 'Analyze'}
            </button>
            {file && (
              <button type="button" className="btn secondary" onClick={() => setFile(null)}>
                Clear
              </button>
            )}
          </div>

          {error && <div className="form-error" style={{ marginTop: 12 }}>{error}</div>}
        </form>
      </div>
    </div>
  )
}
