import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 15000,
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem('zjj_token')
      localStorage.removeItem('zjj_user')
      if (window.location.pathname !== '/') window.location.href = '/'
    }
    return Promise.reject(error)
  },
)
