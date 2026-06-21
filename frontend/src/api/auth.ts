import apiClient from './client'
import type {
  RegisterRequest,
  RegisterResponse,
  TokenResponse,
  UserProfile,
  LoginRequest,
} from '../types'

export async function registerUser(data: RegisterRequest): Promise<RegisterResponse> {
  const response = await apiClient.post<RegisterResponse>('/auth/register', data)
  return response.data
}

export async function loginUser(data: LoginRequest): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>('/auth/login', data)
  return response.data
}

export async function refreshAccessToken(): Promise<{ access_token: string; expires_in: number }> {
  const response = await apiClient.post<{ access_token: string; expires_in: number }>('/auth/refresh')
  return response.data
}

export async function logoutUser(): Promise<void> {
  await apiClient.post('/auth/logout')
}

export async function getCurrentUser(): Promise<UserProfile> {
  const response = await apiClient.get<UserProfile>('/auth/me')
  return response.data
}
