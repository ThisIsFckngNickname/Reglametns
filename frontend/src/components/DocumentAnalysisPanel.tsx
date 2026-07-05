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
  uploaded: 'Р—Р°РіСЂСѓР¶РµРЅ',
  extracting: 'РР·РІР»РµС‡РµРЅРёРµ РїР°СЂР°РіСЂР°С„РѕРІ',
  analyzing: 'LLM-Р°РЅР°Р»РёР· С€Р°РіРѕРІ',
  synthesizing: 'РЎРёРЅС‚РµР· РёРЅСЃР°Р№С‚РѕРІ',
  ready: 'Р“РѕС‚РѕРІРѕ',
  failed: 'РћС€РёР±РєР°',
  cancelled: 'РћС‚РјРµРЅС‘РЅ',
  cancelling: 'РћС‚РјРµРЅР°...',
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

  // РџРѕР»Р»РёРЅРі РґРѕРєСѓРјРµРЅС‚РѕРІ РІ РїСЂРѕС†РµСЃСЃРµ Р°РЅР°Р»РёР·Р°
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

  // Р—Р°РіСЂСѓР·РєР° С„Р°Р№Р»Р°
  const handleFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.docx')) {
      setError('РўРѕР»СЊРєРѕ .docx С„Р°Р№Р»С‹ РїРѕРґРґРµСЂР¶РёРІР°СЋС‚СЃСЏ');
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const result = await uploadDocument(file);
      setPollingIds(prev => new Set(prev).add(result.id));
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'РћС€РёР±РєР° Р·Р°РіСЂСѓР·РєРё');
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
      setError(err instanceof Error ? err.message : 'РћС€РёР±РєР° Р·Р°РїСѓСЃРєР° Р°РЅР°Р»РёР·Р°');
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
      setError(err instanceof Error ? err.message : 'РћС€РёР±РєР° РѕС‚РјРµРЅС‹');
    }
  };

  // РћРїСЂРµРґРµР»РµРЅРёРµ Р°РєС‚РёРІРЅРѕР№ СЃС‚Р°РґРёРё РїР°Р№РїР»Р°Р№РЅР° РґР»СЏ РґРѕРєСѓРјРµРЅС‚Р°
  const getActiveStageIndex = (status: string): number => {
    if (status === 'extracting') return 0;
    if (status === 'analyzing') return 1;
    if (status === 'synthesizing') return 2;
    return -1;
  };

  const getElapsedTime = (createdAt: string): string => {
    const start = new Date(createdAt).getTime();
    const now = Date.now();
    const elapsed = Math.floor((now - start) / 1000);
    if (elapsed < 60) return `${elapsed} сек`;
    const min = Math.floor(elapsed / 60);
    const sec = elapsed % 60;
    return `${min} мин ${sec} сек`;
  };

  const getStuckWarning = (updatedAt: string): string | null => {
    const updated = new Date(updatedAt).getTime();
    const now = Date.now();
    const elapsed = Math.floor((now - updated) / 1000);
    if (elapsed > 30) return `⚠ Нет обновлений ${elapsed} сек — возможно зависло`;
    return null;
  };

  const isInProgress = (status: string) =>
    ['extracting', 'analyzing', 'synthesizing'].includes(status);

  return (
    <div className="document-analysis-panel">
      <h2>РђРЅР°Р»РёР· РґРѕРєСѓРјРµРЅС‚РѕРІ</h2>
      <p className="hint">
        Р—Р°РіСЂСѓР·РёС‚Рµ .docx С„Р°Р№Р» СЂРµРіР»Р°РјРµРЅС‚Р°. РЎРёСЃС‚РµРјР° РёР·РІР»РµС‡С‘С‚ РїР°СЂР°РіСЂР°С„С‹, РїСЂРѕР°РЅР°Р»РёР·РёСЂСѓРµС‚ РёС… С‡РµСЂРµР· LLM
        Рё СЃС„РѕСЂРјРёСЂСѓРµС‚ РёРЅСЃР°Р№С‚С‹ РґР»СЏ СѓР»СѓС‡С€РµРЅРёСЏ РєР°С‡РµСЃС‚РІР° РіРµРЅРµСЂР°С†РёРё.
      </p>

      {/* Drag & Drop Р·РѕРЅР° */}
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
            <p>Р—Р°РіСЂСѓР·РєР°...</p>
          </div>
        ) : (
          <div className="upload-zone-content">
            <span className="upload-icon">рџ“„</span>
            <p className="upload-text">
              <strong>РќР°Р¶РјРёС‚Рµ РґР»СЏ РІС‹Р±РѕСЂР°</strong> РёР»Рё РїРµСЂРµС‚Р°С‰РёС‚Рµ .docx С„Р°Р№Р» СЃСЋРґР°
            </p>
            <p className="upload-hint">РџРѕРґРґРµСЂР¶РёРІР°СЋС‚СЃСЏ С‚РѕР»СЊРєРѕ С„Р°Р№Р»С‹ .docx</p>
          </div>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}

      {/* РЎРїРёСЃРѕРє РґРѕРєСѓРјРµРЅС‚РѕРІ */}
      <div className="documents-list">
        {documents.length === 0 && !uploading && (
          <p className="empty-state">РќРµС‚ Р·Р°РіСЂСѓР¶РµРЅРЅС‹С… РґРѕРєСѓРјРµРЅС‚РѕРІ</p>
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

              {/* Pipeline stages вЂ” РїРѕРєР°Р·С‹РІР°РµРј С‚РѕР»СЊРєРѕ РєРѕРіРґР° РІ РїСЂРѕС†РµСЃСЃРµ РёР»Рё РіРѕС‚РѕРІ/РѕС€РёР±РєР° */}
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
                          {isComplete ? 'вњ“' : isActive ? 'в—Џ' : 'в—‹'}
                        </div>
                        <div className="stage-info">
                          <span className="stage-name">{STATUS_LABELS[stage]}</span>
                          {isActive && (
                            <span className="stage-progress">
                              {stage === 'extracting' && stats?.paragraphs_processed
                                ? `(${stats.paragraphs_processed} РїР°СЂР°РіСЂР°С„РѕРІ)`
                                : stage === 'analyzing' && stats?.total_steps
                                  ? `(${stats.total_steps} С€Р°РіРѕРІ)`
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
                      {doc.status === 'ready' ? 'вњ“' : doc.status === 'failed' ? 'вњ—' : 'в—‹'}
                    </div>
                    <div className="stage-info">
                      <span className="stage-name">
                        {doc.status === 'ready' ? 'Р“РѕС‚РѕРІРѕ' : doc.status === 'failed' ? 'РћС€РёР±РєР°' : 'Р—Р°РІРµСЂС€РµРЅРёРµ'}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {inProgress && (
                <div className="progress-details">
                  <span className="elapsed-time">⏱ {getElapsedTime(doc.created_at)}</span>
                  {getStuckWarning(doc.updated_at) && (
                    <span className="stuck-warning">{getStuckWarning(doc.updated_at)}</span>
                  )}
                </div>
              )}

              {/* Р”РµР№СЃС‚РІРёСЏ */}
              <div className="document-actions">
                {doc.status === 'uploaded' && (
                  <button
                    className="btn btn-primary btn-small"
                    onClick={() => handleAnalyze(doc.id)}
                  >
                    рџ”Ќ Р—Р°РїСѓСЃС‚РёС‚СЊ Р°РЅР°Р»РёР·
                  </button>
                )}
                {inProgress && (
                  <button
                    className="btn btn-cancel btn-small"
                    onClick={() => handleCancel(doc.id)}
                  >
                    вњ• РћС‚РјРµРЅРёС‚СЊ
                  </button>
                )}
                {doc.status === 'cancelled' && (
                  <span className="cancelled-text">вЏ№ РђРЅР°Р»РёР· РѕС‚РјРµРЅС‘РЅ</span>
                )}
                {(doc.status === 'ready' || doc.status === 'failed') && (
                  <button
                    className="btn btn-small"
                    onClick={() => setExpandedId(expandedId === doc.id ? null : doc.id)}
                  >
                    {expandedId === doc.id ? 'в–ј РЎРєСЂС‹С‚СЊ' : 'в–¶ Р РµР·СѓР»СЊС‚Р°С‚С‹'}
                  </button>
                )}
              </div>

              {/* Р РµР·СѓР»СЊС‚Р°С‚С‹ РґР»СЏ ready/failed */}
              {expandedId === doc.id && doc.status === 'ready' && doc.insights && (
                <div className="document-insights">
                  <div className="insight-section">
                    <h4>рџ“Љ РЎС‚Р°С‚РёСЃС‚РёРєР°</h4>
                    <p>РџР°СЂР°РіСЂР°С„РѕРІ: {doc.total_paragraphs} | РЁР°РіРѕРІ: {doc.total_steps}</p>
                  </div>
                  {doc.insights.step_templates && Array.isArray(doc.insights.step_templates) && (
                    <div className="insight-section">
                      <h4>рџ“ќ РЁР°Р±Р»РѕРЅС‹ РїСЂРµРґР»РѕР¶РµРЅРёР№</h4>
                      <ul>
                        {doc.insights.step_templates.map((tpl: string, i: number) => (
                          <li key={i}><code>{tpl}</code></li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {doc.insights.vocabulary && typeof doc.insights.vocabulary === 'object' && (
                    <div className="insight-section">
                      <h4>рџ“– РЎР»РѕРІР°СЂСЊ С‚РµСЂРјРёРЅРѕРІ</h4>
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
                      <h4>вљ™пёЏ РџСЂР°РІРёР»Р° Р»РѕРіРёРєРё</h4>
                      <pre>{JSON.stringify(doc.insights.logic_rules, null, 2)}</pre>
                    </div>
                  )}
                </div>
              )}
              {expandedId === doc.id && doc.status === 'failed' && (
                <div className="document-insights">
                  <div className="insight-section">
                    <h4>вќЊ РћС€РёР±РєР°</h4>
                    <p className="error-text">{doc.error_message || 'РќРµРёР·РІРµСЃС‚РЅР°СЏ РѕС€РёР±РєР°'}</p>
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

