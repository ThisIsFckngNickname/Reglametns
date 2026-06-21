import apiClient from './client'
import type {
  Company,
  CompanyCreate,
  CompanyUpdate,
  CompanyProfile,
  SetCompanyRequest,
  SetCompanyResponse,
} from '../types'

export async function getCompanies(): Promise<Company[]> {
  const response = await apiClient.get<Company[]>('/companies')
  return response.data
}

export async function createCompany(data: CompanyCreate): Promise<Company> {
  const response = await apiClient.post<Company>('/companies', data)
  return response.data
}

export async function updateCompany(
  id: number,
  data: CompanyUpdate
): Promise<Company> {
  const response = await apiClient.put<Company>(`/companies/${id}`, data)
  return response.data
}

export async function deleteCompany(id: number): Promise<void> {
  await apiClient.delete(`/companies/${id}`)
}

export async function setActiveCompany(
  data: SetCompanyRequest
): Promise<SetCompanyResponse> {
  const response = await apiClient.put<SetCompanyResponse>('/user/company', data)
  return response.data
}

export async function getCompanyProfile(id: number): Promise<CompanyProfile> {
  const response = await apiClient.get<CompanyProfile>(`/companies/${id}/profile`)
  return response.data
}

export async function updateCompanyProfile(
  id: number,
  data: Partial<Pick<CompanyProfile, 'name' | 'inn' | 'legal_form' | 'active_sources'>>
): Promise<CompanyProfile> {
  const response = await apiClient.put<CompanyProfile>(`/companies/${id}/profile`, data)
  return response.data
}
