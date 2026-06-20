import apiClient from './client'
import type { DocumentVersion } from '../types'

export async function createDocumentVersion(
  documentId: number,
  file: File,
  versionNotes?: string,
  onProgress?: (percent: number) => void
): Promise<DocumentVersion> {
  const formData = new FormData()
  formData.append('file', file)
  if (versionNotes) formData.append('version_notes', versionNotes)

  const response = await apiClient.post(`/documents/${documentId}/versions`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded * 100) / e.total))
      }
    },
  })
  return response.data
}

export async function getDocumentDiff(
  documentId: number,
  fromVersion: number,
  toVersion: number
): Promise<{ from_version: number; to_version: number; changes: Array<{ field: string; old_value: string | null; new_value: string | null }> }> {
  const response = await apiClient.get(`/documents/${documentId}/diff`, {
    params: { from: fromVersion, to: toVersion },
  })
  return response.data
}
