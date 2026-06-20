import apiClient from './client'
import type {
  LegislationResult,
  LegislationSource,
  LegislationSourceCreate,
  LegislationSourceSearchResult,
  AvailableSource,
} from '../types'

export async function getAvailableSources(): Promise<AvailableSource[]> {
  const response = await apiClient.get<AvailableSource[]>('/legislation/sources/available')
  return response.data
}

export async function searchLegislation(
  query: string,
  source?: string,
  page?: number
): Promise<LegislationResult> {
  const response = await apiClient.get('/legislation/search', {
    params: { query, source, page },
  })
  return response.data
}

export async function getLegislationSources(): Promise<LegislationSource[]> {
  const response = await apiClient.get('/legislation/sources')
  return response.data
}

export async function createLegislationSource(
  data: LegislationSourceCreate
): Promise<LegislationSource> {
  const response = await apiClient.post('/legislation/sources', data)
  return response.data
}

export async function getLegislationSource(
  id: number
): Promise<LegislationSource> {
  const response = await apiClient.get(`/legislation/sources/${id}`)
  return response.data
}

export async function updateLegislationSource(
  id: number,
  data: Partial<LegislationSourceCreate>
): Promise<LegislationSource> {
  const response = await apiClient.put(`/legislation/sources/${id}`, data)
  return response.data
}

export async function deleteLegislationSource(id: number): Promise<void> {
  await apiClient.delete(`/legislation/sources/${id}`)
}

export async function searchInLegislationSource(
  id: number,
  query: string
): Promise<LegislationSourceSearchResult[]> {
  const response = await apiClient.post(
    `/legislation/sources/${id}/search`,
    { query }
  )
  return response.data
}
