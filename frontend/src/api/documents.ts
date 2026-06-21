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

export async function deleteDocument(id: number): Promise<void> {
  await apiClient.delete(`/documents/admin/documents/${id}`)
}

export async function getDocumentVersions(id: number): Promise<{ items: DocumentVersion[] }> {
  const response = await apiClient.get(`/documents/${id}/versions`)
  const data = response.data
  return { items: Array.isArray(data) ? data : data.items ?? [] }
}

export function getDownloadUrl(versionId: number): string {
  return `${apiClient.defaults.baseURL}/documents/versions/${versionId}/download`
}

export async function downloadDocumentVersion(
  versionId: number,
  filename?: string
): Promise<void> {
  const response = await apiClient.get(`/documents/versions/${versionId}/download`, {
    responseType: 'blob',
  })

  // Determine filename: if caller provided one, use it;
  // otherwise try Content-Disposition header, then fallback
  let finalFilename = filename || ''
  if (!finalFilename) {
    const contentDisposition = response.headers['content-disposition']
    if (contentDisposition) {
      const match = contentDisposition.match(/filename[^;=\n]*=["']?([^"';\n]*)["']?/)
      if (match && match[1]) {
        finalFilename = match[1]
      }
    }
  }
  if (!finalFilename) {
    // Determine extension from response content-type
    const contentType = String(response.headers['content-type'] || '')
    let ext = 'docx'
    if (contentType.includes('pdf')) ext = 'pdf'
    else if (contentType.includes('octet-stream')) ext = 'docx'
    finalFilename = `document-${versionId}.${ext}`
  }

  const url = window.URL.createObjectURL(new Blob([response.data]))
  const a = document.createElement('a')
  a.href = url
  a.download = finalFilename
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(url)
}

export async function getDocumentSections(id: number): Promise<{ sections: DocumentSection[] }> {
  const response = await apiClient.get(`/documents/${id}/sections`)
  const data = response.data
  return { sections: Array.isArray(data) ? data : data.sections ?? [] }
}

export async function getDocumentTerms(id: number): Promise<{ terms: DocumentTerm[] }> {
  const response = await apiClient.get(`/documents/${id}/terms`)
  const data = response.data
  return { terms: Array.isArray(data) ? data : data.terms ?? [] }
}

export async function getDocumentAbbreviations(id: number): Promise<{ abbreviations: DocumentAbbreviation[] }> {
  const response = await apiClient.get(`/documents/${id}/abbreviations`)
  const data = response.data
  return { abbreviations: Array.isArray(data) ? data : data.abbreviations ?? [] }
}

export async function getDocumentTables(id: number): Promise<{ tables: DocumentTable[] }> {
  const response = await apiClient.get(`/documents/${id}/tables`)
  const data = response.data
  return { tables: Array.isArray(data) ? data : data.tables ?? [] }
}
