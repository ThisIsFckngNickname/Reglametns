import apiClient from './client'
import type {
  Holding,
  HoldingCreate,
  HoldingUpdate,
  HoldingProfile,
  SetHoldingRequest,
  SetHoldingResponse,
} from '../types'

export async function getHoldings(): Promise<Holding[]> {
  const response = await apiClient.get<Holding[]>('/holdings')
  return response.data
}

export async function createHolding(data: HoldingCreate): Promise<Holding> {
  const response = await apiClient.post<Holding>('/holdings', data)
  return response.data
}

export async function updateHolding(
  id: number,
  data: HoldingUpdate
): Promise<Holding> {
  const response = await apiClient.put<Holding>(`/holdings/${id}`, data)
  return response.data
}

export async function deleteHolding(id: number): Promise<void> {
  await apiClient.delete(`/holdings/${id}`)
}

export async function setActiveHolding(
  data: SetHoldingRequest
): Promise<SetHoldingResponse> {
  const response = await apiClient.put<SetHoldingResponse>('/user/holding', data)
  return response.data
}

export async function getHoldingProfile(id: number): Promise<HoldingProfile> {
  const response = await apiClient.get<HoldingProfile>(`/holdings/${id}/profile`)
  return response.data
}

export async function updateHoldingProfile(
  id: number,
  data: Partial<Pick<HoldingProfile, 'name' | 'inn' | 'legal_form' | 'active_sources'>>
): Promise<HoldingProfile> {
  const response = await apiClient.put<HoldingProfile>(`/holdings/${id}/profile`, data)
  return response.data
}
