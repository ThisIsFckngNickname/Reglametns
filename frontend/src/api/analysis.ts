import apiClient from './client'

export const getAnalysisHistory = (documentId: number) =>
  apiClient.get(`/documents/${documentId}/analyses`)

export const getAnalysisStatus = (analysisId: number) =>
  apiClient.get(`/analysis/${analysisId}/status`)

export const reanalyzeDocument = (documentId: number) =>
  apiClient.post(`/documents/${documentId}/reanalyze`)
