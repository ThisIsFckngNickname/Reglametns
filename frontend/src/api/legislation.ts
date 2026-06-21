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
    timeout: 15000, // 15 second timeout to prevent infinite loading
  })

  const data = response.data

  // Backend may return 'items' (correct) or 'results' (old format)
  if (data && !data.items && data.results) {
    return {
      query: data.query || query,
      source: data.source || source || '',
      items: data.results.map((r: any) => ({
        title: r.title || '',
        number: r.document_number || null,
        date: r.document_date || null,
        source: r.source || '',
        url: r.url || '',
        snippet: r.snippet || '',
      })),
      total: data.total || data.results.length || 0,
      page: data.page || page || 1,
    }
  }

  // Normalise items if they exist
  if (data && Array.isArray(data.items)) {
    return {
      query: data.query || query,
      source: data.source || source || '',
      items: data.items.map((item: any) => ({
        title: item.title || '',
        number: item.number || item.document_number || null,
        date: item.date || item.document_date || null,
        source: item.source || '',
        url: item.url || '',
        snippet: item.snippet || '',
      })),
      total: data.total || data.items.length || 0,
      page: data.page || page || 1,
    }
  }

  // Fallback empty result
  return {
    query: query,
    source: source || '',
    items: [],
    total: 0,
    page: page || 1,
  }
}

/**
 * Converts a string to a positive number hash.
 * Used as fallback id when the backend returns string ids.
 */
function simpleStringHash(s: string): number {
  let hash = 0
  for (let i = 0; i < s.length; i++) {
    const chr = s.charCodeAt(i)
    hash = (hash << 5) - hash + chr
    hash |= 0 // Convert to 32bit integer
  }
  return Math.abs(hash)
}

/**
 * Fetches legislation sources from the backend.
 *
 * Handles two response formats:
 * 1. Backend (real API):  { sources: Array<{id: string, name, description, base_url, enabled}> }
 * 2. MSW (mock):          Array<LegislationSource>  (plain array)
 *
 * If the format is unrecognised, returns an empty array as a graceful fallback.
 */
export async function getLegislationSources(): Promise<LegislationSource[]> {
  const response = await apiClient.get('/legislation/sources')
  const data = response.data

  // MSW path – already a plain array of LegislationSource
  if (Array.isArray(data)) {
    return data
  }

  // Backend path – wrapped in { sources: [...] }
  if (data && typeof data === 'object' && Array.isArray(data.sources)) {
    return data.sources.map((s: {
      id: string
      name: string
      description: string
      base_url: string
      enabled: boolean
    }): LegislationSource => ({
      id: parseInt(s.id, 10) || simpleStringHash(s.id),
      holding_id: 0,
      name: s.name,
      source_type: 'template_url',
      url_template: s.base_url,
      parser_type: null,
      selector: null,
      is_active: s.enabled,
      is_paid: false,
      icon_url: null,
      description: s.description,
      created_at: '',
      updated_at: '',
    }))
  }

  // Unexpected format – graceful fallback
  return []
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
