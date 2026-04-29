import { useEffect, useState } from 'react'
import { statsApi } from '../api.js'

const fmtDate = (iso) => {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

export default function ProfilePage() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    statsApi.me()
      .then(({ data }) => setStats(data))
      .catch(() => setStats(null))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="profile-page">
        <div className="profile-card">
          <div className="profile-skeleton" style={{ width: 180, height: 14 }} />
          <div className="profile-skeleton" style={{ width: 120, height: 11, marginTop: 12 }} />
        </div>
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="profile-page">
        <div className="profile-card"><div className="empty">Failed to load</div></div>
      </div>
    )
  }

  const maxCount = Math.max(1, ...(stats.topStyles?.map((s) => s.count) || [0]))

  return (
    <div className="profile-page">
      <div className="profile-grid">
        <div className="profile-card">
          <div className="panel-label">Account</div>
          <div className="profile-email">{stats.email}</div>
          <div className="profile-since">Since {fmtDate(stats.memberSince)}</div>
        </div>

        <div className="profile-card">
          <div className="panel-label">Library</div>
          <div className="big-number">{stats.totalPhotos}</div>
          <div className="profile-status-row">
            <span className="status-pill DONE">
              <span className="status-dot DONE" /> Done {stats.byStatus.DONE}
            </span>
            <span className="status-pill PENDING">
              <span className="status-dot PENDING" /> Pending {stats.byStatus.PENDING}
            </span>
            <span className="status-pill FAILED">
              <span className="status-dot FAILED" /> Failed {stats.byStatus.FAILED}
            </span>
          </div>
        </div>

        <div className="profile-card profile-styles">
          <div className="panel-label">Styles in your library</div>
          {stats.topStyles.length === 0 ? (
            <div className="similar-empty" style={{ marginTop: 12 }}>No analyzed photos yet</div>
          ) : (
            <div className="profile-style-list">
              {stats.topStyles.map((s) => (
                <div className="style-stat-row" key={s.name}>
                  <span className="name">{s.name.replace('_', ' ')}</span>
                  <span className="bar">
                    <span className="fill" style={{ width: `${(s.count / maxCount) * 100}%` }} />
                  </span>
                  <span className="count">{s.count}</span>
                  <span className="avg">{Math.round(s.avgConfidence * 100)}%</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
