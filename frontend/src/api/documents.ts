import apiClient from './client'
import type {
  DocumentListItem, DocumentDetail, DocumentVersion,
  DocumentSection, DocumentTerm, DocumentAbbreviation,
  DocumentTable, UploadResponse, PaginatedResponse,
  DocumentStatus,
} from '../types'

export async function uploadDocument(
  file: File,
  title?: string,
  description?: string,
  onProgress?: (percent: number) => void
): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  if (title) formData.append('title', title)
  if (description) formData.append('description', description)

  const response = await apiClient.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded * 100) / e.total))
      }
    },
  })
  return response.data
}

export async function getDocuments(params?: {
  status?: DocumentStatus
  search?: string
  page?: number
  page_size?: number
}): Promise<PaginatedResponse<DocumentListItem>> {
  const response = await apiClient.get('/documents', { params })
  return response.data
}

export async function getDocument(id: number): Promise<DocumentDetail> {
  const response = await apiClient.get(`/documents/${id}`)
  return response.data
}

export async function updateDocument(
  id: number,
  data: { title?: string; description?: string; status?: DocumentStatus }
): Promise<DocumentDetail> {
  const response = await apiClient.put(`/documents/${id}`, data)
  return response.data
}

export async function archiveDocument(id: number): Promise<void> {
  await apiClient.delete(`/documents/${id}`)
}

export async function getDocumentVersions(id: number): Promise<{ items: DocumentVersion[] }> {
  const response = await apiClient.get(`/documents/${id}/versions`)
  return response.data
}

export function getDownloadUrl(versionId: number): string {
  return `${apiClient.defaults.baseURL}/documents/versions/${versionId}/download`
}

export async function getDocumentSections(id: number): Promise<{ sections: DocumentSection[] }> {
  const response = await apiClient.get(`/documents/${id}/sections`)
  return response.data
}

export async function getDocumentTerms(id: number): Promise<{ terms: DocumentTerm[] }> {
  const response = await apiClient.get(`/documents/${id}/terms`)
  return response.data
}

export async function getDocumentAbbreviations(id: number): Promise<{ abbreviations: DocumentAbbreviation[] }> {
  const response = await apiClient.get(`/documents/${id}/abbreviations`)
  return response.data
}

export async function getDocumentTables(id: number): Promise<{ tables: DocumentTable[] }> {
  const response = await apiClient.get(`/documents/${id}/tables`)
  return response.data
}
