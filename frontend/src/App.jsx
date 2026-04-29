import { NavLink, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { useAuth } from './AuthContext.jsx'
import LoginPage from './routes/LoginPage.jsx'
import RegisterPage from './routes/RegisterPage.jsx'
import GalleryPage from './routes/GalleryPage.jsx'
import UploadPage from './routes/UploadPage.jsx'
import ProfilePage from './routes/ProfilePage.jsx'

function NavBar() {
  const { isAuthed, email, logout } = useAuth()
  const navigate = useNavigate()
  const onLogout = () => { logout(); navigate('/login') }

  return (
    <nav className="nav">
      <div className="nav-left">
        <span className="logo-mark" aria-hidden />
        <span className="brand">Spectr</span>
      </div>
      <div className="nav-right">
        {isAuthed ? (
          <>
            <NavLink to="/" end className={({ isActive }) => isActive ? 'active' : ''}>Gallery</NavLink>
            <NavLink to="/upload" className={({ isActive }) => isActive ? 'active' : ''}>Upload</NavLink>
            <NavLink to="/profile" className={({ isActive }) => isActive ? 'active' : ''}>Profile</NavLink>
            <span className="email">{email}</span>
            <button className="logout" onClick={onLogout}>Logout</button>
          </>
        ) : (
          <>
            <NavLink to="/login" className={({ isActive }) => isActive ? 'active' : ''}>Login</NavLink>
            <NavLink to="/register" className={({ isActive }) => isActive ? 'active' : ''}>Register</NavLink>
          </>
        )}
      </div>
    </nav>
  )
}

function RequireAuth({ children }) {
  const { isAuthed } = useAuth()
  return isAuthed ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <>
      <NavBar />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/" element={<RequireAuth><GalleryPage /></RequireAuth>} />
        <Route path="/upload" element={<RequireAuth><UploadPage /></RequireAuth>} />
        <Route path="/profile" element={<RequireAuth><ProfilePage /></RequireAuth>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}
