import apiClient from './client'
import type { AdminUserCreate, AdminUserUpdate, AdminUserResponse } from '../types'

export async function getAdminUsers(): Promise<AdminUserResponse[]> {
  const response = await apiClient.get<AdminUserResponse[]>('/user/admin/users')
  return response.data
}

export async function createAdminUser(data: AdminUserCreate): Promise<AdminUserResponse> {
  const response = await apiClient.post<AdminUserResponse>('/user/admin/users', data)
  return response.data
}

export async function updateAdminUser(
  id: number,
  data: AdminUserUpdate
): Promise<AdminUserResponse> {
  const response = await apiClient.put<AdminUserResponse>(`/user/admin/users/${id}`, data)
  return response.data
}

export async function deleteAdminUser(id: number): Promise<void> {
  await apiClient.delete(`/user/admin/users/${id}`)
}

export async function banUser(id: number): Promise<void> {
  await apiClient.put(`/user/admin/users/${id}/ban`)
}

export async function unbanUser(id: number): Promise<void> {
  await apiClient.put(`/user/admin/users/${id}/unban`)
}

export async function setUserCompanyRole(
  userId: number,
  companyId: number,
  role: string
): Promise<void> {
  await apiClient.put(`/user/admin/users/${userId}/companies/${companyId}?role=${role}`)
}
