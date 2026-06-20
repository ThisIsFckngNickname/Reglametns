import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import type { ApiError } from '../types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const USE_MSW = import.meta.env.VITE_USE_MSW === 'true'

const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Send cookies (httpOnly refresh_token) with every request
})

// Request interceptor: attach access token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: handle 401 and refresh via httpOnly cookie
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean
    }

    // If 401 and not already retried, attempt token refresh via cookie
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/refresh') &&
      !originalRequest.url?.includes('/auth/login') &&
      !originalRequest.url?.includes('/auth/logout') &&
      !originalRequest.url?.includes('/auth/verify-login')
    ) {
      originalRequest._retry = true

      try {
        // The refresh_token httpOnly cookie is sent automatically
        const { data } = await axios.post(
          `${BASE_URL}/auth/refresh`,
          {},
          { withCredentials: true }
        )
        const newAccessToken = data.access_token
        localStorage.setItem('access_token', newAccessToken)
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newAccessToken}`
        }
        return apiClient(originalRequest)
      } catch (refreshError) {
        // Refresh failed — clear tokens and redirect to login
        localStorage.removeItem('access_token')
        window.location.href = '/login'
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  }
)

// Helper to extract error message from API response
export function getApiErrorMessage(error: unknown): string {
  if (error instanceof AxiosError && error.response?.data) {
    const errData = error.response.data as ApiError
    if (errData.detail?.message) {
      return errData.detail.message
    }
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'Произошла неизвестная ошибка'
}

export { USE_MSW }
export default apiClient
