export interface AnalysisStepStatus {
  status: 'waiting' | 'running' | 'done' | 'error'
  started_at: string | null
  completed_at: string | null
  error: string | null
}

export interface AnalysisStatusResponse {
  id: number
  document_id: number
  document_version_id: number | null
  file_hash: string | null
  status: 'running' | 'complete' | 'error'
  steps_status: Record<string, AnalysisStepStatus>
  error_message: string | null
  result_summary: {
    sections_found?: number
    terms_found?: number
    abbreviations_found?: number
    references_found?: number
    chunks_indexed?: number
    style_analyzed?: boolean
    total_steps?: number
    failed_steps?: number
    completed_steps?: number
  } | null
  created_at: string
  completed_at: string | null
}

export interface AnalysisHistoryItem {
  id: number
  document_id: number
  document_version_id: number | null
  status: 'running' | 'complete' | 'error'
  error_message: string | null
  result_summary: AnalysisStatusResponse['result_summary'] | null
  created_at: string
  completed_at: string | null
}

export interface ReanalyzeResponse {
  analysis_id: number
  document_id: number
  status: string
  message: string
}

export type AnalysisStatus = 'none' | 'running' | 'complete' | 'error'
