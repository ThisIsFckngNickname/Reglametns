import apiClient from './client'
import type { DocumentLink } from '../types'

export async function getDocumentLinks(documentId: number): Promise<{ items: DocumentLink[] }> {
  const response = await apiClient.get(`/documents/${documentId}/links`)
  const data = response.data
  return { items: Array.isArray(data) ? data : data.items ?? [] }
}

export async function createDocumentLink(
  documentId: number,
  data: { target_document_id: number; link_type: string; description?: string }
): Promise<DocumentLink> {
  const response = await apiClient.post(`/documents/${documentId}/links`, data)
  return response.data
}

export async function deleteDocumentLink(linkId: number): Promise<void> {
  await apiClient.delete(`/documents/links/${linkId}`)
}
