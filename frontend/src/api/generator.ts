import apiClient from './client'
import type { GenerateResponse } from '../types'

export async function generateDocument(
  context: string,
  draftFiles?: File[],
  influencingDocumentIds?: number[],
  onProgress?: (step: string, percent: number) => void,
): Promise<GenerateResponse> {
  const formData = new FormData()
  formData.append('context', context)

  if (draftFiles?.length) {
    draftFiles.forEach((file) => formData.append('draft_files', file))
  }

  if (influencingDocumentIds?.length) {
    formData.append('influencing_document_ids', JSON.stringify(influencingDocumentIds))
  }

  // Simulate progress steps (real backend would send events)
  onProgress?.('preparing', 10)

  const response = await apiClient.post('/generator/generate', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 600000,  // 10 minutes for generation (slow Ollama)
    onDownloadProgress: () => {
      onProgress?.('generating', 50)
    },
  })

  onProgress?.('formatting', 90)
  return response.data
}
