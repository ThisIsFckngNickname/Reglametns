// ============================================================
// API Client — все вызовы к backend
// ============================================================

import type { GenerationStatus, DocumentInfo, ProviderInfo, CompanyProfile, ParagraphAnalysis } from '../types';

const API_BASE = '/api';

// ============================================================
// Error class
// ============================================================
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(`API Error ${status}: ${message}`);
    this.name = 'ApiError';
  }
}

/**
 * Запуск multi-stage генерации.
 * POST /api/generate/multi
 */
export async function startGeneration(
  topic: string,
  provider?: string,
  companyProfileId?: string
): Promise<{ generation_id: string; status: string }> {
  const body: Record<string, string> = { topic, provider: provider ?? 'auto' };
  if (companyProfileId) {
    body.company_profile_id = companyProfileId;
  }
  const res = await fetch(`${API_BASE}/generate/multi`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new ApiError(res.status, errBody?.detail || (await res.text()));
  }

  return res.json();
}

/**
 * Получение статуса генерации.
 * GET /api/generate/{id}/status
 */
export async function getGenerationStatus(
  id: string
): Promise<GenerationStatus> {
  const res = await fetch(`${API_BASE}/generate/${id}/status`);

  if (res.status === 404) {
    throw new ApiError(404, 'Generation session not found');
  }
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }

  return res.json();
}

/**
 * Получение URL для скачивания документа.
 * GET /api/documents/{id}/download
 */
export function getDocumentDownloadUrl(documentId: string): string {
  return `${API_BASE}/documents/${documentId}/download`;
}

/**
 * Список документов (история, до 20 шт).
 * GET /api/documents
 */
export async function listDocuments(): Promise<DocumentInfo[]> {
  const res = await fetch(`${API_BASE}/documents`);
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }
  const data = await res.json();
  // Backend returns { items: [...], total: N }
  if (data && Array.isArray(data.items)) {
    return data.items;
  }
  if (Array.isArray(data)) {
    return data;
  }
  return [];
}

/**
 * Список доступных провайдеров.
 * GET /api/providers
 */
export async function listProviders(): Promise<ProviderInfo[]> {
  const res = await fetch(`${API_BASE}/providers`);
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }
  const data = await res.json();
  // Backend returns { providers: [...] }
  if (data && Array.isArray(data.providers)) {
    return data.providers;
  }
  if (Array.isArray(data)) {
    return data;
  }
  return [];
}

/**
 * Polling статуса генерации.
 *
 * - Опрашивает /api/generate/{id}/status каждые intervalMs
 * - Вызывает onProgress на каждый успешный ответ
 * - Завершается, когда status === 'completed' или status === 'failed'
 * - При ошибке сети — повторяет попытку (не прерывает polling)
 *
 * @param signal — AbortSignal для отмены (cleanup при размонтировании)
 */
export async function pollGenerationStatus(
  generationId: string,
  onProgress: (status: GenerationStatus) => void,
  signal?: AbortSignal,
  intervalMs: number = 3000,
): Promise<GenerationStatus> {
  let cancelled = false;

  if (signal) {
    signal.addEventListener('abort', () => { cancelled = true; }, { once: true });
  }

  const poll = async (): Promise<GenerationStatus> => {
    if (cancelled) {
      throw new DOMException('Polling cancelled', 'AbortError');
    }

    try {
      const status = await getGenerationStatus(generationId);

      if (cancelled) throw new DOMException('Polling cancelled', 'AbortError');

      onProgress(status);

      if (status.status === 'completed' || status.status === 'failed') {
        return status;
      }

      // Продолжить polling
      await new Promise(resolve => setTimeout(resolve, intervalMs));
      return poll();
    } catch (err) {
      // Если отмена — не рекурсировать
      if (cancelled || (err instanceof DOMException && err.name === 'AbortError')) {
        throw err;
      }

      // Сетевая ошибка — подождать и повторить
      console.warn('Polling error, retrying in 5s:', err);
      await new Promise(resolve => setTimeout(resolve, 5000));
      return poll();
    }
  };

  return poll();
}

// ============================================================
// Stage 6.6 — Company Profile API
// ============================================================

/**
 * Загрузка документов для создания профиля компании.
 * POST /api/company-profiles/upload
 */
export async function uploadCompanyDocs(
  name: string,
  files: File[],
  description?: string
): Promise<{ profile_id: string; name: string; document_count: number; status: string }> {
  const formData = new FormData();
  formData.append('name', name);
  for (const f of files) {
    formData.append('files', f);
  }
  if (description) {
    formData.append('description', description);
  }
  const res = await fetch(`${API_BASE}/company-profiles/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new ApiError(res.status, errBody?.detail || (await res.text()));
  }
  return res.json();
}

/**
 * Запуск анализа профиля компании.
 * POST /api/company-profiles/{id}/analyze
 */
export async function analyzeProfile(
  profileId: string
): Promise<{ profile_id: string; status: string; estimated_seconds: number }> {
  const res = await fetch(`${API_BASE}/company-profiles/${profileId}/analyze`, {
    method: 'POST',
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new ApiError(res.status, errBody?.detail || (await res.text()));
  }
  return res.json();
}

/**
 * Получение профиля компании с документами и статистикой.
 * GET /api/company-profiles/{id}
 */
export async function getProfile(profileId: string): Promise<CompanyProfile> {
  const res = await fetch(`${API_BASE}/company-profiles/${profileId}`);
  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new ApiError(res.status, errBody?.detail || (await res.text()));
  }
  return res.json();
}

/**
 * Получение параграфов с анализом для профиля.
 * GET /api/company-profiles/{id}/paragraphs
 */
export async function getProfileParagraphs(
  profileId: string,
  params?: { section?: string; document_id?: string; limit?: number; offset?: number }
): Promise<{ items: ParagraphAnalysis[]; total: number }> {
  const query = new URLSearchParams();
  if (params?.section) query.set('section', params.section);
  if (params?.document_id) query.set('document_id', params.document_id);
  if (params?.limit !== undefined) query.set('limit', String(params.limit));
  if (params?.offset !== undefined) query.set('offset', String(params.offset));
  const qs = query.toString();
  const url = `${API_BASE}/company-profiles/${profileId}/paragraphs${qs ? '?' + qs : ''}`;
  const res = await fetch(url);
  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new ApiError(res.status, errBody?.detail || (await res.text()));
  }
  return res.json();
}

/**
 * Список профилей компании.
 * GET /api/company-profiles
 */
export async function listProfiles(
  params?: { status?: string; profile_type?: string; limit?: number; offset?: number }
): Promise<{ items: CompanyProfile[]; total: number }> {
  const query = new URLSearchParams();
  if (params?.status) query.set('status', params.status);
  if (params?.profile_type) query.set('profile_type', params.profile_type);
  if (params?.limit !== undefined) query.set('limit', String(params.limit));
  if (params?.offset !== undefined) query.set('offset', String(params.offset));
  const qs = query.toString();
  const url = `${API_BASE}/company-profiles${qs ? '?' + qs : ''}`;
  const res = await fetch(url);
  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new ApiError(res.status, errBody?.detail || (await res.text()));
  }
  return res.json();
}

/**
 * Удаление профиля компании.
 * DELETE /api/company-profiles/{id}
 */
export async function deleteProfile(profileId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/company-profiles/${profileId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new ApiError(res.status, errBody?.detail || (await res.text()));
  }
}

/**
 * Получение URL для скачивания документа из профиля.
 * GET /api/company-profiles/{id}/download/{doc_id}
 */
export function getProfileDownloadUrl(profileId: string, docId: string): string {
  return `${API_BASE}/company-profiles/${profileId}/download/${docId}`;
}
