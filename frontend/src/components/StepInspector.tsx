import React, { useState, useEffect, useCallback } from 'react';
import { getProfileParagraphs } from '../api/client';
import type { ParagraphAnalysis, UploadedDocItem } from '../types';

interface StepInspectorProps {
  profileId: string;
  documents: UploadedDocItem[];
}

const PAGE_SIZE = 10;

export default function StepInspector({ profileId, documents }: StepInspectorProps) {
  const [paragraphs, setParagraphs] = useState<ParagraphAnalysis[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [filterDoc, setFilterDoc] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  const fetchParagraphs = useCallback(
    async (newOffset: number) => {
      setLoading(true);
      setError(null);
      try {
        const data = await getProfileParagraphs(profileId, {
          document_id: filterDoc,
          limit: PAGE_SIZE,
          offset: newOffset,
        });
        setParagraphs(data.items);
        setTotal(data.total);
        setOffset(newOffset);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Ошибка загрузки параграфов'
        );
      } finally {
        setLoading(false);
      }
    },
    [profileId, filterDoc]
  );

  useEffect(() => {
    fetchParagraphs(0);
  }, [fetchParagraphs]);

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div className="inspector">
      <h4>Параграфы ({total})</h4>

      <div className="inspector-filters">
        <select
          className="input-field"
          value={filterDoc || ''}
          onChange={(e) => setFilterDoc(e.target.value || undefined)}
        >
          <option value="">Все документы</option>
          {documents.map((d) => (
            <option key={d.id} value={d.id}>
              {d.original_name}
            </option>
          ))}
        </select>
      </div>

      {loading && <div className="loading">Загрузка...</div>}
      {error && <div className="error-message">{error}</div>}

      {!loading && !error && paragraphs.length === 0 && (
        <div className="history-empty">
          <p>Нет параграфов для отображения</p>
        </div>
      )}

      {paragraphs.map((p) => (
        <div key={p.id} className="paragraph-card">
          <div className="paragraph-header">
            <span className="paragraph-index">#{p.paragraph_index}</span>
            {p.section_title && (
              <span className="paragraph-section">{p.section_title}</span>
            )}
            <span className="paragraph-chars">{p.char_count} зн.</span>
          </div>
          <div className="paragraph-text">{p.original_text}</div>
          {p.steps.length > 0 && (
            <div className="steps-list">
              {p.steps.map((step, idx) => (
                <div key={idx} className="step-entry">
                  {step.role && (
                    <span className="step-field field-role">{step.role}</span>
                  )}
                  {step.action && (
                    <span className="step-field field-action">
                      {step.action}
                    </span>
                  )}
                  {step.deadline && (
                    <span className="step-field field-deadline">
                      {step.deadline}
                    </span>
                  )}
                  {step.method && (
                    <span className="step-field field-method">
                      {step.method}
                    </span>
                  )}
                  {step.condition && (
                    <span className="step-field field-condition">
                      {step.condition}
                    </span>
                  )}
                  {step.document && (
                    <span className="step-field field-document">
                      {step.document}
                    </span>
                  )}
                  {step.consequence && (
                    <span className="step-field field-consequence">
                      {step.consequence}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}

      {totalPages > 1 && (
        <div className="pagination">
          <button
            type="button"
            className="btn btn-small btn-secondary"
            disabled={currentPage <= 1 || loading}
            onClick={() => fetchParagraphs(offset - PAGE_SIZE)}
          >
            ← Назад
          </button>
          <span className="pagination-info">
            {currentPage} / {totalPages}
          </span>
          <button
            type="button"
            className="btn btn-small btn-secondary"
            disabled={currentPage >= totalPages || loading}
            onClick={() => fetchParagraphs(offset + PAGE_SIZE)}
          >
            Вперёд →
          </button>
        </div>
      )}
    </div>
  );
}
