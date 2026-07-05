// ============================================================
// Stage 3 � Multi-stage support
// ============================================================

/** ������ ������ ������ ��������� */
export interface GenerationStatus {
  id: string;
  topic: string;
  status: GenerationStage;
  current_stage: string;       // ���������������� �������� �����
  stage_progress: number;      // 0�100
  total_sections: number;
  completed_sections: number;
  provider_used?: string;
  document_id?: string | null;
  error_message?: string | null;
  created_at: string;          // ISO8601
  updated_at?: string;
  completed_at?: string | null; // ISO8601, ������ ��� status === "completed"
}

/** ��������� ������� ������ ��������� */
export type GenerationStage =
  | 'accepted'
  | 'planning'
  | 'annotating'
  | 'generating'
  | 'auditing'
  | 'assembling'
  | 'completed'
  | 'failed';

/** ���������� � ��������� ��� ������ ������� */
export interface DocumentInfo {
  id: string;
  topic: string;
  provider_used: string;
  status?: string;
  created_at: string;          // ISO8601
}

/** ���������� � ��������� AI-���������� */
export interface ProviderInfo {
  id: string;
  name: string;
  model: string;
  available: boolean;
}

/** ������������ ���������� (���������) */
export interface AppState {
  // ������� ���������
  currentGeneration: GenerationStatus | null;
  // ������� �� polling
  isPolling: boolean;
  // ������� ����������
  history: DocumentInfo[];
  // ��������� ����������
  providers: ProviderInfo[];
  // ���������� ������ (�� ��������� � ���������� ����������)
  globalError: string | null;
  // ���� ��������� ��������
  isLoading: boolean;
}

/** ���������������� �������� ������ */
export const STAGE_LABELS: Record<string, string> = {
  accepted: '������ � ���������',
  planning: '����������� �����',
  annotating: '������������� ��������',
  generating: '��������� ��������',
  auditing: '����� ���������',
  assembling: '������ ���������',
  completed: '������',
  failed: '������',
};

/** ����� ������ ��� progress bar / label */
export const STAGE_COLORS: Record<string, string> = {
  accepted: '#6b7280',     // gray
  planning: '#3b82f6',     // blue
  annotating: '#8b5cf6',   // purple
  generating: '#f59e0b',   // amber
  auditing: '#ef4444',     // red
  assembling: '#10b981',   // green
  completed: '#10b981',    // green
  failed: '#ef4444',       // red
};

/** ������� ������ ��� ����������� � �������� */
export const STAGE_ORDER: GenerationStage[] = [
  'accepted',
  'planning',
  'annotating',
  'generating',
  'auditing',
  'assembling',
  'completed',
];

/** �������������� �������� ���������� ��� ����������� */
export function formatProviderName(providerId: string): string {
  switch (providerId) {
    case 'generation':
      return '������������';
    case 'ollama':
      return 'Ollama (���������)';
    case 'groq':
      return 'Groq Cloud';
    case 'yandexgpt':
      return 'YandexGPT';
    case 'auto':
      return 'Auto';
    default:
      return providerId;
  }
}

// ============================================================
// Stage 7 � Document Analysis (replaces Company Profile)
// ============================================================

/** ������ ������� ��������� */
export type AnalysisStatus = 'uploaded' | 'extracting' | 'analyzing' | 'synthesizing' | 'ready' | 'cancelled' | 'cancelling' | 'failed';

/** ����� �� POST /api/documents/upload */
export interface UploadResponse {
  id: string;
  original_filename: string;
  status: AnalysisStatus;
  message: string;
}

/** ����� �� POST /api/documents/{id}/analyze */
export interface AnalyzeResponse {
  id: string;
  status: string;
  message: string;
}

/** ����� �� GET /api/documents/{id} � ������� ������ */
export interface DocumentAnalysis {
  id: string;
  original_filename: string;
  file_size: number;
  status: AnalysisStatus;
  total_paragraphs: number;
  total_steps: number;
  insights?: Record<string, unknown> | null;
  stats?: Record<string, unknown> | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}
