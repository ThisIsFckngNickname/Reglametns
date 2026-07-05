import React, { useState, useEffect, useCallback } from 'react';
import {
  uploadDocument,
  analyzeDocument,
  getDocumentAnalysis,
  listDocumentAnalyses,
} from '../api/client';
import type { DocumentAnalysis, AnalysisStatus } from '../types';

const STATUS_LABELS: Record<AnalysisStatus, string> = {
  uploaded: 'Загружен',
  extracting: 'Извлечение параграфов...',
  analyzing: 'Анализ...',
  ready: 'Готово',
  failed: 'Ошибка',
};

export default function DocumentAnalysisPanel() {
  const [documents, setDocuments] = useState<DocumentAnalysis[]>([]);
  const [uploading, setUploading] = useState(false);
  const [pollingIds, setPollingIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const loadDocuments = useCallback(async () => {
    try {
      const docs = await listDocumentAnalyses();
      setDocuments(docs);
    } catch (err) {
      console.error('Failed to load documents:', err);
    }
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  // Poll documents that are in progress
  useEffect(() => {
    if (pollingIds.size === 0) return;
    const interval = setInterval(async () => {
      let changed = false;
      const newPolling = new Set(pollingIds);
      for (const id of pollingIds) {
        try {
          const doc = await getDocumentAnalysis(id);
          if (doc.status === 'ready' || doc.status === 'failed') {
            newPolling.delete(id);
            changed = true;
          }
        } catch {
          // keep polling
        }
      }
      if (changed) {
        setPollingIds(newPolling);
        await loadDocuments();
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [pollingIds, loadDocuments]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.docx')) {
      setError('Только .docx файлы поддерживаются');
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const result = await uploadDocument(file);
      setPollingIds(prev => new Set(prev).add(result.id));
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки');
    } finally {
      setUploading(false);
    }
  };

  const handleAnalyze = async (id: string) => {
    setError(null);
    try {
      await analyzeDocument(id);
      setPollingIds(prev => new Set(prev).add(id));
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка запуска анализа');
    }
  };

  return (
    <div className="document-analysis-panel">
      <h2>Анализ документов</h2>
      <p className="hint">
        Загрузите .docx файл регламента. Система извлечёт параграфы, проанализирует их через LLM
        и сформирует инсайты для улучшения качества генерации.
      </p>

      <div className="upload-section">
        <label className="btn btn-primary">
          {uploading ? 'Загрузка...' : '📄 Загрузить .docx'}
          <input
            type="file"
            accept=".docx"
            onChange={handleFileUpload}
            disabled={uploading}
            hidden
          />
        </label>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="documents-list">
        {documents.length === 0 && !uploading && (
          <p className="empty-state">Нет загруженных документов</p>
        )}

        {documents.map((doc) => (
          <div key={doc.id} className="document-card">
            <div className="document-header">
              <span className="document-name">{doc.original_filename}</span>
              <span className={`status-badge status-${doc.status}`}>
                {STATUS_LABELS[doc.status]}
              </span>
              <span className="document-size">
                {(doc.file_size / 1024).toFixed(1)} KB
              </span>
            </div>

            <div className="document-actions">
              {doc.status === 'uploaded' && (
                <button
                  className="btn btn-small"
                  onClick={() => handleAnalyze(doc.id)}
                >
                  🔍 Анализировать
                </button>
              )}
              {(doc.status === 'extracting' || doc.status === 'analyzing') && (
                <span className="analyzing-indicator">⏳ Анализ выполняется...</span>
              )}
              {doc.status === 'ready' && (
                <button
                  className="btn btn-small"
                  onClick={() => setExpandedId(expandedId === doc.id ? null : doc.id)}
                >
                  {expandedId === doc.id ? '▼ Скрыть' : '▶ Результаты'}
                </button>
              )}
              {doc.status === 'failed' && (
                <span className="error-text">❌ {doc.error_message || 'Ошибка анализа'}</span>
              )}
            </div>

            {expandedId === doc.id && doc.status === 'ready' && doc.insights && (
              <div className="document-insights">
                <div className="insight-section">
                  <h4>📊 Статистика</h4>
                  <p>Параграфов: {doc.total_paragraphs} | Шагов: {doc.total_steps}</p>
                </div>

                {doc.insights.step_templates && Array.isArray(doc.insights.step_templates) && (
                  <div className="insight-section">
                    <h4>📝 Шаблоны предложений</h4>
                    <ul>
                      {doc.insights.step_templates.map((tpl: string, i: number) => (
                        <li key={i}><code>{tpl}</code></li>
                      ))}
                    </ul>
                  </div>
                )}

                {doc.insights.vocabulary && typeof doc.insights.vocabulary === 'object' && (
                  <div className="insight-section">
                    <h4>📖 Словарь терминов</h4>
                    <div className="vocabulary-grid">
                      {Object.entries(doc.insights.vocabulary as Record<string, unknown>).map(([category, items]) => (
                        <div key={category} className="vocab-category">
                          <strong>{category}</strong>
                          <span className="vocab-items">
                            {typeof items === 'object'
                              ? Object.keys(items as Record<string, unknown>).slice(0, 10).join(', ')
                              : Array.isArray(items)
                                ? (items as string[]).slice(0, 10).join(', ')
                                : String(items).slice(0, 100)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {doc.insights.logic_rules && typeof doc.insights.logic_rules === 'object' && (
                  <div className="insight-section">
                    <h4>⚙️ Правила логики</h4>
                    <pre>{JSON.stringify(doc.insights.logic_rules, null, 2)}</pre>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
