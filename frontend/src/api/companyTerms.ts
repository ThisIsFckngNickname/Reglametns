import apiClient from './client'
import type { CompanyTerm, CompanyAbbreviation, PaginatedTermsResponse } from '../types/companyTerms'

// ─── Terms CRUD ───────────────────────────────────────────────────────

export async function getTerms(
  params?: { q?: string; page?: number; page_size?: number }
): Promise<PaginatedTermsResponse<CompanyTerm>> {
  const response = await apiClient.get('/terms', {
    params: {
      search: params?.q,
      page: params?.page || 1,
      page_size: params?.page_size || 20,
    },
  })
  return response.data
}

export async function createTerm(data: {
  term: string
  definition: string
}): Promise<CompanyTerm> {
  const response = await apiClient.post('/terms', data)
  return response.data
}

export async function updateTerm(
  id: number,
  data: { term?: string; definition?: string }
): Promise<CompanyTerm> {
  const response = await apiClient.put(`/terms/${id}`, data)
  return response.data
}

export async function deleteTerm(id: number): Promise<void> {
  await apiClient.delete(`/terms/${id}`)
}

// ─── Abbreviations CRUD ───────────────────────────────────────────────

export async function getAbbreviations(
  params?: { q?: string; page?: number; page_size?: number }
): Promise<PaginatedTermsResponse<CompanyAbbreviation>> {
  const response = await apiClient.get('/abbreviations', {
    params: {
      search: params?.q,
      page: params?.page || 1,
      page_size: params?.page_size || 20,
    },
  })
  return response.data
}

export async function createAbbreviation(data: {
  abbreviation: string
  full_form: string
}): Promise<CompanyAbbreviation> {
  const response = await apiClient.post('/abbreviations', data)
  return response.data
}

export async function updateAbbreviation(
  id: number,
  data: { abbreviation?: string; full_form?: string }
): Promise<CompanyAbbreviation> {
  const response = await apiClient.put(`/abbreviations/${id}`, data)
  return response.data
}

export async function deleteAbbreviation(id: number): Promise<void> {
  await apiClient.delete(`/abbreviations/${id}`)
}
