const SIZE_PATTERN = [
  '', '', 'w2', '', 'h2', '',
  'w2 h2', '', '', 'h2', '', 'w2',
  '', '', 'h2', '', 'w2', '', '',
]

export function cellClass(index) {
  return SIZE_PATTERN[index % SIZE_PATTERN.length]
}

export default function PhotoCell({ photo, index, onClick }) {
  const extra = cellClass(index)
  const topTags = (photo.styles || []).slice(0, 2)

  return (
    <div
      className={`cell ${extra}`}
      onClick={() => onClick?.(photo)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter') onClick?.(photo) }}
    >
      <span className={`status-dot ${photo.status}`} />
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
