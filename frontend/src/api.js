import axios from 'axios'

export const api = axios.create({
  baseURL: '/api',
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const status = err.response?.status
    // 401 — нет/невалидный токен, 403 — токен валиден, но прав нет (для нашего API
    // на практике означает то же самое, поскольку других ролей пока не вводили)
    if (status === 401 || status === 403) {
      localStorage.removeItem('token')
      localStorage.removeItem('email')
      if (!window.location.pathname.startsWith('/login') &&
          !window.location.pathname.startsWith('/register')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  },
)

export const authApi = {
  register: (email, password) => api.post('/auth/register', { email, password }),
  login: (email, password) => api.post('/auth/login', { email, password }),
}

export const photoApi = {
  upload: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post('/photos', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  uploadWithProgress: (file, onProgress) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post('/photos', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (e.total && onProgress) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    })
  },
  list: (page = 0, size = 20) => api.get('/photos', { params: { page, size } }),
  get: (id) => api.get(`/photos/${id}`),
  delete: (id) => api.delete(`/photos/${id}`),
  search: (style, minConfidence = 0.2, page = 0, size = 20) =>
    api.get('/photos/search', { params: { style, minConfidence, page, size } }),
}

export const styleApi = {
  list: () => api.get('/styles'),
}

export const statsApi = {
  me: () => api.get('/stats/me'),
}
