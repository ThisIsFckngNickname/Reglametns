import React, { useState, useEffect } from 'react';
import type { ProviderInfo, DocumentAnalysis } from '../types';
import { listDocumentAnalyses } from '../api/client';

interface GeneratorFormProps {
  providers: ProviderInfo[];
  disabled: boolean;
  onStartGeneration: (topic: string, provider: string, isMulti: boolean, documentId?: string) => Promise<void>;
  onCancelGeneration: () => void;
}

const MAX_TOPIC_LENGTH = 2000;

export default function GeneratorForm({
  providers,
  disabled,
  onStartGeneration,
  onCancelGeneration,
}: GeneratorFormProps) {
  const [topic, setTopic] = useState('');
  const [provider, setProvider] = useState('auto');
  const [isGenerating, setIsGenerating] = useState(false);
  const [validationError, setValidationError] = useState('');
  const [analyzedDocs, setAnalyzedDocs] = useState<DocumentAnalysis[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>('');

  useEffect(() => {
    listDocumentAnalyses()
      .then((docs) => {
        const readyDocs = docs.filter((d) => d.status === 'ready');
        setAnalyzedDocs(readyDocs);
      })
      .catch(() => {
        // non-critical � no docs to load
      });
  }, []);

  const topicTrimmed = topic.trim();
  const isTopicEmpty = topicTrimmed.length === 0;
  const isTopicTooLong = topicTrimmed.length > MAX_TOPIC_LENGTH;

  const handleTopicChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTopic(e.target.value);
    if (validationError) setValidationError('');
  };

  const handleGenerate = async (isMulti: boolean) => {
    // Validation
    if (isTopicEmpty) {
      setValidationError('������� ���� ����������');
      return;
    }
    if (isTopicTooLong) {
      setValidationError(`���� ������� ������� (����. ${MAX_TOPIC_LENGTH} ��������)`);
      return;
    }

    // Check provider availability for non-multi mode
    if (!isMulti) {
      const selectedProvider = providers.find(p => p.id === provider);
      if (selectedProvider && !selectedProvider.available) {
        setValidationError('��������� ��������� ����������');
        return;
      }
    }

    setIsGenerating(true);
    setValidationError('');

    try {
      // Pass document_id only for multi-stage generation
      const docId = isMulti ? (selectedDocumentId || undefined) : undefined;
      await onStartGeneration(topicTrimmed, provider, isMulti, docId);
    } catch (err) {
      setValidationError(err instanceof Error ? err.message : '������ ���������');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCancel = () => {
    setIsGenerating(false);
    onCancelGeneration();
  };

  return (
    <div className="card generator-form">
      <h2>�������� ����������</h2>

      <div className="form-group">
        <label htmlFor="topic-input">���� ����������</label>
        <input
          id="topic-input"
          type="text"
          value={topic}
          onChange={handleTopicChange}
          placeholder="������� ���� ���������� (��������, ��������� �� ����� ���)"
          disabled={isGenerating || disabled}
          className="input-field"
          maxLength={MAX_TOPIC_LENGTH + 100}
        />
        <div className="input-hint">
          {topic.length > MAX_TOPIC_LENGTH * 0.8 ? (
            <span className="char-count warn">{topic.length}/{MAX_TOPIC_LENGTH}</span>
          ) : (
            <span className="char-count">{topic.length}/{MAX_TOPIC_LENGTH}</span>
          )}
        </div>
      </div>

      <div className="form-group">
        <label htmlFor="provider-select">���������</label>
        <select
          id="provider-select"
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
          disabled={isGenerating || disabled}
          className="input-field"
        >
          {providers.map((p) => (
            <option key={p.id} value={p.id} disabled={!p.available}>
              {p.name}{!p.available ? ' (����������)' : ''}
            </option>
          ))}
        </select>
      </div>

      {analyzedDocs.length > 0 && (
        <div className="form-group">
          <label htmlFor="document-select">�������� �� ������� ���������</label>
          <select
            id="document-select"
            value={selectedDocumentId}
            onChange={(e) => setSelectedDocumentId(e.target.value)}
            disabled={isGenerating || disabled}
            className="input-field"
          >
            <option value="">��� ���������</option>
            {analyzedDocs.map((doc) => (
              <option key={doc.id} value={doc.id}>
                {doc.original_filename} ({doc.total_paragraphs} ����������, {doc.total_steps} �����)
              </option>
            ))}
          </select>
        </div>
      )}

      {validationError && (
        <div className="error-message">{validationError}</div>
      )}

      <div className="form-actions">
        {isGenerating || disabled ? (
          <button
            type="button"
            className="btn btn-cancel"
            onClick={handleCancel}
          >
            ? ������
          </button>
        ) : (
          <>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => handleGenerate(false)}
              disabled={isTopicEmpty}
            >
              Generate (single-stage)
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => handleGenerate(true)}
              disabled={isTopicEmpty}
            >
              ?? Generate multi-stage (�������������)
            </button>
          </>
        )}
      </div>

      {isGenerating && (
        <div className="generating-indicator">
          <span className="spinner" />
          ���������...
        </div>
      )}

      {!isGenerating && !disabled && (
        <p className="form-note">
          ������������� ��� ������� �����������
        </p>
      )}
    </div>
  );
}
