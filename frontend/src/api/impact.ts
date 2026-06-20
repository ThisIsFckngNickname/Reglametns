import apiClient from './client'
import type { ImpactMap, ImpactGraph } from '../types'

export async function getImpactMap(documentId: number): Promise<ImpactMap> {
  const response = await apiClient.get(`/documents/${documentId}/impact`)
  return response.data
}

export async function getImpactGraph(documentId: number): Promise<ImpactGraph> {
  const response = await apiClient.get(`/documents/${documentId}/impact/graph`)
  return response.data
}
