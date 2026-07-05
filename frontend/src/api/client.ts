// ============================================================
// API Client � ��� ������ � backend
// ============================================================

import type { GenerationStatus, DocumentInfo, ProviderInfo, UploadResponse, AnalyzeResponse, DocumentAnalysis } from '../types';

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
 * ������ multi-stage ���������.
 * POST /api/generate/multi
 */
export async function startGeneration(
  topic: string,
  provider?: string,
  documentId?: string,
): Promise<{ generation_id: string; status: string }> {
  const body: Record<string, string> = { topic, provider: provider ?? 'auto' };
  if (documentId) {
    body.document_id = documentId;
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
 * ��������� ������� ���������.
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
 * ��������� URL ��� ���������� ���������.
 * GET /api/documents/{id}/download
 */
export function getDocumentDownloadUrl(documentId: string): string {
  return `${API_BASE}/documents/${documentId}/download`;
}

/**
 * ������ ���������� (�������, �� 20 ��).
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
 * ������ ��������� �����������.
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
 * Polling ������� ���������.
 *
 * - ���������� /api/generate/{id}/status ������ intervalMs
 * - �������� onProgress �� ������ �������� �����
 * - �����������, ����� status === 'completed' ��� status === 'failed'
 * - ��� ������ ���� � ��������� ������� (�� ��������� polling)
 *
 * @param signal � AbortSignal ��� ������ (cleanup ��� ���������������)
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

      // ���������� polling
      await new Promise(resolve => setTimeout(resolve, intervalMs));
      return poll();
    } catch (err) {
      // ���� ������ � �� �������������
      if (cancelled || (err instanceof DOMException && err.name === 'AbortError')) {
        throw err;
      }

      // ������� ������ � ��������� � ���������
      console.warn('Polling error, retrying in 5s:', err);
      await new Promise(resolve => setTimeout(resolve, 5000));
      return poll();
    }
  };

  return poll();
}

// ============================================================
// Stage 7 � Document Analysis API
// ============================================================

/**
 * �������� .docx ����� ��� �������.
 * POST /api/analyses/upload
 */
export async function uploadDocument(
  file: File
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/analyses/upload`, {
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
 * ������ ������� ��������� (background).
 * POST /api/analyses/{id}/analyze
 */
export async function analyzeDocument(
  id: string
): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/analyses/${id}/analyze`, {
    method: 'POST',
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new ApiError(res.status, errBody?.detail || (await res.text()));
  }
  return res.json();
}

/**
 * ��������� ������� � ����������� �������.
 * GET /api/analyses/{id}
 */
export async function getDocumentAnalysis(
  id: string
): Promise<DocumentAnalysis> {
  const res = await fetch(`${API_BASE}/analyses/${id}`);
  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new ApiError(res.status, errBody?.detail || (await res.text()));
  }
  return res.json();
}

/**
 * ������ ���� ���������� � ��������.
 * GET /api/analyses
 */
export async function listDocumentAnalyses(): Promise<DocumentAnalysis[]> {
  const res = await fetch(`${API_BASE}/analyses`);
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }
  const data = await res.json();
  if (data && Array.isArray(data.documents)) {
    return data.documents;
  }
  return [];
}

/**
 * ������ ������� ���������.
 * POST /api/analyses/{id}/cancel
 */
export async function cancelAnalysis(id: string): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/analyses/${id}/cancel`, {
    method: 'POST',
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new ApiError(res.status, errBody?.detail || (await res.text()));
  }
  return res.json();
}
