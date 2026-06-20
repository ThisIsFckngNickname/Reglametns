import apiClient from './client'
import type {
  RegisterRequest,
  RegisterResponse,
  VerifyRequest,
  VerifyResponse,
  TokenResponse,
  UserProfile,
  LoginRequest,
} from '../types'

export async function registerUser(data: RegisterRequest): Promise<RegisterResponse> {
  const response = await apiClient.post<RegisterResponse>('/auth/register', data)
  return response.data
}

export async function verifyRegistration(data: VerifyRequest): Promise<VerifyResponse> {
  const response = await apiClient.post<VerifyResponse>('/auth/verify-registration', data)
  return response.data
}

export async function loginUser(data: LoginRequest): Promise<{ message: string }> {
  const response = await apiClient.post<{ message: string }>('/auth/login', data)
  return response.data
}

export async function verifyLogin(data: VerifyRequest): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>('/auth/verify-login', data)
  return response.data
}

/**
 * Refresh access token using httpOnly cookie (set by backend on login).
 * No manual refresh_token needed — cookie is sent automatically.
 */
export async function refreshAccessToken(): Promise<{ access_token: string; expires_in: number }> {
  const response = await apiClient.post<{ access_token: string; expires_in: number }>('/auth/refresh')
  return response.data
}

/**
 * Logout — calls backend to clear the httpOnly refresh_token cookie.
 */
export async function logoutUser(): Promise<void> {
  await apiClient.post('/auth/logout')
}

export async function getCurrentUser(): Promise<UserProfile> {
  const response = await apiClient.get<UserProfile>('/auth/me')
  return response.data
}
