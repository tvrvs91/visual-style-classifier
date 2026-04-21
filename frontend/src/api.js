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
    if (err.response?.status === 401) {
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
  list: (page = 0, size = 20) => api.get('/photos', { params: { page, size } }),
  get: (id) => api.get(`/photos/${id}`),
  search: (style, minConfidence = 0.2, page = 0, size = 20) =>
    api.get('/photos/search', { params: { style, minConfidence, page, size } }),
}

export const styleApi = {
  list: () => api.get('/styles'),
}
