// ============================================================
// Stage 3 — Multi-stage support
// ============================================================

/** Полный статус сессии генерации */
export interface GenerationStatus {
  id: string;
  topic: string;
  status: GenerationStage;
  current_stage: string;       // Человекочитаемое название этапа
  stage_progress: number;      // 0–100
  total_sections: number;
  completed_sections: number;
  provider_used?: string;
  document_id?: string | null;
  error_message?: string | null;
  created_at: string;          // ISO8601
  updated_at?: string;
  completed_at?: string | null; // ISO8601, только при status === "completed"
}

/** Возможные статусы этапов генерации */
export type GenerationStage =
  | 'accepted'
  | 'planning'
  | 'annotating'
  | 'generating'
  | 'auditing'
  | 'assembling'
  | 'completed'
  | 'failed';

/** Информация о документе для списка истории */
export interface DocumentInfo {
  id: string;
  topic: string;
  provider_used: string;
  status?: string;
  created_at: string;          // ISO8601
}

/** Информация о доступном AI-провайдере */
export interface ProviderInfo {
  id: string;
  name: string;
  model: string;
  available: boolean;
}

/** Конфигурация приложения (состояние) */
export interface AppState {
  // Текущая генерация
  currentGeneration: GenerationStatus | null;
  // Активен ли polling
  isPolling: boolean;
  // История документов
  history: DocumentInfo[];
  // Доступные провайдеры
  providers: ProviderInfo[];
  // Глобальная ошибка (не связанная с конкретной генерацией)
  globalError: string | null;
  // Флаг начальной загрузки
  isLoading: boolean;
}

/** Человекочитаемые названия этапов */
export const STAGE_LABELS: Record<string, string> = {
  accepted: 'Принят в обработку',
  planning: 'Составление плана',
  annotating: 'Аннотирование разделов',
  generating: 'Генерация разделов',
  auditing: 'Аудит связности',
  assembling: 'Сборка документа',
  completed: 'Готово',
  failed: 'Ошибка',
};

/** Цвета этапов для progress bar / label */
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

/** Порядок этапов для отображения в чеклисте */
export const STAGE_ORDER: GenerationStage[] = [
  'accepted',
  'planning',
  'annotating',
  'generating',
  'auditing',
  'assembling',
  'completed',
];

/** Форматирование названия провайдера для отображения */
export function formatProviderName(providerId: string): string {
  switch (providerId) {
    case 'generation':
      return 'Многоэтапная';
    case 'ollama':
      return 'Ollama (локальный)';
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
// Stage 6.6 — Company Profile
// ============================================================

export interface Step {
  role: string | null;
  action: string | null;
  deadline: string | null;
  method: string | null;
  condition: string | null;
  document: string | null;
  consequence: string | null;
}

export interface ParagraphAnalysis {
  id: string;
  paragraph_index: number;
  section_title: string | null;
  original_text: string;
  char_count: number;
  is_table_row: boolean;
  is_list_item: boolean;
  steps: Step[];
}

export interface AnalysisStats {
  // Live progress fields (present during analysis)
  phase?: 'extracting' | 'analyzing' | 'synthesizing' | 'ready' | 'failed';
  batch?: number;
  total_batches?: number;
  paragraphs_processed?: number;
  total_paragraphs?: number;
  last_batch_at?: string;
  detail?: string;
  error_message?: string;

  // Statistics fields (present after completion)
  total_steps?: number;
  paragraphs_with_role_pct?: number;
  paragraphs_with_deadline_pct?: number;
  paragraphs_with_method_pct?: number;
  paragraphs_with_condition_pct?: number;
  paragraphs_with_document_pct?: number;
  paragraphs_with_consequence_pct?: number;
  avg_steps_per_paragraph?: number;
}

export interface CompanyProfile {
  profile_id: string;
  name: string;
  description?: string;
  profile_type: string;
  document_count: number;
  status: 'uploaded' | 'extracting' | 'analyzing' | 'synthesizing' | 'ready' | 'failed';
  progress_pct: number;
  profile_json?: unknown;
  analysis_stats?: AnalysisStats;
  documents: UploadedDocItem[];
  created_at: string;
  updated_at: string;
}

export interface UploadedDocItem {
  id: string;
  original_name: string;
  file_size: number;
  paragraph_count: number;
  step_count: number;
  status: string;
}
