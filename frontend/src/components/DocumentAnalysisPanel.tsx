import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  uploadDocument,
  analyzeDocument,
  getDocumentAnalysis,
  listDocumentAnalyses,
  cancelAnalysis,
} from '../api/client';
import type { DocumentAnalysis, AnalysisStatus } from '../types';

// Stages in order for pipeline visualization
const PIPELINE_STAGES: AnalysisStatus[] = ['extracting', 'analyzing', 'synthesizing'];

const STATUS_LABELS: Record<string, string> = {
  uploaded: 'Загружен',
  extracting: 'Извлечение параграфов',
  analyzing: 'LLM-анализ шагов',
  synthesizing: 'Синтез инсайтов',
  ready: 'Готово',
  failed: 'Ошибка',
  cancelled: 'Отменён',
  cancelling: 'Отмена...',
};

export default function DocumentAnalysisPanel() {
  const [documents, setDocuments] = useState<DocumentAnalysis[]>([]);
  const [uploading, setUploading] = useState(false);
  const [pollingIds, setPollingIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  // Поллинг документов в процессе анализа
  useEffect(() => {
    if (pollingIds.size === 0) return;
    const interval = setInterval(async () => {
      let changed = false;
      const newPolling = new Set(pollingIds);
      for (const id of pollingIds) {
        try {
          const doc = await getDocumentAnalysis(id);
          if (['ready', 'failed', 'cancelled'].includes(doc.status)) {
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
    }, 2000);
    return () => clearInterval(interval);
  }, [pollingIds, loadDocuments]);

  // Загрузка файла
  const handleFile = async (file: File) => {
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

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  // Drag & Drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(true);
  };
  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  };
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
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

  const handleCancel = async (id: string) => {
    setError(null);
    try {
      await cancelAnalysis(id);
      setPollingIds(prev => {
        const next = new Set(prev);
        next.add(id);
        return next;
      });
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка отмены');
    }
  };

  // Определение активной стадии пайплайна для документа
  const getActiveStageIndex = (status: string): number => {
    if (status === 'extracting') return 0;
    if (status === 'analyzing') return 1;
    if (status === 'synthesizing') return 2;
    return -1;
  };

  const isInProgress = (status: string) =>
    ['extracting', 'analyzing', 'synthesizing'].includes(status);

  return (
    <div className="document-analysis-panel">
      <h2>Анализ документов</h2>
      <p className="hint">
        Загрузите .docx файл регламента. Система извлечёт параграфы, проанализирует их через LLM
        и сформирует инсайты для улучшения качества генерации.
      </p>

      {/* Drag & Drop зона */}
      <div
        className={`upload-zone ${dragOver ? 'drag-over' : ''} ${uploading ? 'uploading' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !uploading && fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".docx"
          onChange={handleFileInput}
          disabled={uploading}
          hidden
        />
        {uploading ? (
          <div className="upload-zone-content">
            <span className="upload-spinner" />
            <p>Загрузка...</p>
          </div>
        ) : (
          <div className="upload-zone-content">
            <span className="upload-icon">📄</span>
            <p className="upload-text">
              <strong>Нажмите для выбора</strong> или перетащите .docx файл сюда
            </p>
            <p className="upload-hint">Поддерживаются только файлы .docx</p>
          </div>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}

      {/* Список документов */}
      <div className="documents-list">
        {documents.length === 0 && !uploading && (
          <p className="empty-state">Нет загруженных документов</p>
        )}

        {documents.map((doc) => {
          const activeStage = getActiveStageIndex(doc.status);
          const inProgress = isInProgress(doc.status);
          const stats = doc.stats as Record<string, unknown> | null;

          return (
            <div key={doc.id} className="document-card">
              <div className="document-header">
                <span className="document-name">{doc.original_filename}</span>
                <span className="document-size">
                  {(doc.file_size / 1024).toFixed(1)} KB
                </span>
              </div>

              {/* Pipeline stages — показываем только когда в процессе или готов/ошибка */}
              {(inProgress || doc.status === 'ready' || doc.status === 'failed' || doc.status === 'cancelled') && (
                <div className="pipeline-stages">
                  {PIPELINE_STAGES.map((stage, idx) => {
                    const isActive = idx === activeStage;
                    const isComplete = idx < activeStage || doc.status === 'ready' || (doc.status === 'failed' && idx < activeStage);
                    const isPending = idx > activeStage && doc.status !== 'ready' && doc.status !== 'failed' && doc.status !== 'cancelled';

                    return (
                      <div
                        key={stage}
                        className={`pipeline-stage ${isActive ? 'active' : ''} ${isComplete ? 'complete' : ''} ${isPending ? 'pending' : ''}`}
                      >
                        <div className="stage-indicator">
                          {isComplete ? '✓' : isActive ? '●' : '○'}
                        </div>
                        <div className="stage-info">
                          <span className="stage-name">{STATUS_LABELS[stage]}</span>
                          {isActive && (
                            <span className="stage-progress">
                              {stage === 'extracting' && stats?.paragraphs_processed
                                ? `(${stats.paragraphs_processed} параграфов)`
                                : stage === 'analyzing' && stats?.total_steps
                                  ? `(${stats.total_steps} шагов)`
                                  : '...'}
                            </span>
                          )}
                          {isActive && <span className="stage-spinner" />}
                        </div>
                      </div>
                    );
                  })}
                  <div className={`pipeline-stage ${doc.status === 'ready' ? 'complete' : doc.status === 'failed' ? 'failed' : 'pending'}`}>
                    <div className="stage-indicator">
                      {doc.status === 'ready' ? '✓' : doc.status === 'failed' ? '✗' : '○'}
                    </div>
                    <div className="stage-info">
                      <span className="stage-name">
                        {doc.status === 'ready' ? 'Готово' : doc.status === 'failed' ? 'Ошибка' : 'Завершение'}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Действия */}
              <div className="document-actions">
                {doc.status === 'uploaded' && (
                  <button
                    className="btn btn-primary btn-small"
                    onClick={() => handleAnalyze(doc.id)}
                  >
                    🔍 Запустить анализ
                  </button>
                )}
                {inProgress && (
                  <button
                    className="btn btn-cancel btn-small"
                    onClick={() => handleCancel(doc.id)}
                  >
                    ✕ Отменить
                  </button>
                )}
                {doc.status === 'cancelled' && (
                  <span className="cancelled-text">⏹ Анализ отменён</span>
                )}
                {(doc.status === 'ready' || doc.status === 'failed') && (
                  <button
                    className="btn btn-small"
                    onClick={() => setExpandedId(expandedId === doc.id ? null : doc.id)}
                  >
                    {expandedId === doc.id ? '▼ Скрыть' : '▶ Результаты'}
                  </button>
                )}
              </div>

              {/* Результаты для ready/failed */}
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
              {expandedId === doc.id && doc.status === 'failed' && (
                <div className="document-insights">
                  <div className="insight-section">
                    <h4>❌ Ошибка</h4>
                    <p className="error-text">{doc.error_message || 'Неизвестная ошибка'}</p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
