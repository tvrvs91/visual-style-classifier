const SIZE_PATTERN = [
  '', '', 'w2', '', 'h2', '',
  'w2 h2', '', '', 'h2', '', 'w2',
  '', '', 'h2', '', 'w2', '', '',
]

export function cellClass(index) {
  return SIZE_PATTERN[index % SIZE_PATTERN.length]
}

export default function PhotoCell({ photo, index, onClick, onDelete }) {
  const extra = cellClass(index)
  const topTags = (photo.styles || []).slice(0, 2)

  const handleDelete = (e) => {
    e.stopPropagation()
    if (window.confirm('Delete this photo?')) onDelete?.(photo)
  }

  return (
    <div
      className={`cell ${extra}`}
      onClick={() => onClick?.(photo)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter') onClick?.(photo) }}
    >
      <span className={`status-dot ${photo.status}`} />
      {onDelete && (
        <button className="cell-delete" onClick={handleDelete} aria-label="Delete">×</button>
      )}
      {photo.url
        ? <img src={photo.url} alt="" loading="lazy" />
        : <div style={{ width: '100%', height: '100%', background: '#0a0a0a' }} />
      }
      <div className="overlay">
        {topTags.map((t) => (
          <span className="tag" key={t.name}>{t.name}</span>
        ))}
      </div>
    </div>
  )
}
