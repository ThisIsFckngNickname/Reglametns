import React from 'react';
import type { GenerationStatus } from '../types';
import { formatProviderName } from '../types';
import { getDocumentDownloadUrl } from '../api/client';

interface ResultPanelProps {
  status: GenerationStatus;
  onGenerateNew: () => void;
}

function formatDuration(createdAt: string, completedAt?: string | null): string {
  if (!createdAt) return '�';
  const start = new Date(createdAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();
  const totalSeconds = Math.max(0, Math.floor((end - start) / 1000));
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  if (m > 0) {
    return `${m} ��� ${s} ���`;
  }
  return `${s} ���`;
}

export default function ResultPanel({
  status,
  onGenerateNew,
}: ResultPanelProps) {
  const hasDocumentId = status.document_id && status.document_id !== null;

  return (
    <div className="card result-panel">
      <h2>? ��������� ������� ������!</h2>

      <div className="result-details">
        <div className="result-row">
          <span className="result-label">?? ����:</span>
          <span className="result-value">{status.topic}</span>
        </div>
        <div className="result-row">
          <span className="result-label">? ���������:</span>
          <span className="result-value">
            {formatProviderName(status.provider_used || '')}
          </span>
        </div>
        <div className="result-row">
          <span className="result-label">?? ��������:</span>
          <span className="result-value">{status.total_sections}</span>
        </div>
        <div className="result-row">
          <span className="result-label">? �����:</span>
          <span className="result-value">
            {formatDuration(status.created_at, status.completed_at)}
          </span>
        </div>
      </div>

      <div className="result-actions">
        {hasDocumentId ? (
          <a
            href={getDocumentDownloadUrl(status.document_id!)}
            className="btn btn-primary"
            download
          >
            ? ������� .docx
          </a>
        ) : (
          <div className="error-message">
            ������: ID ��������� �� �������
          </div>
        )}

        <button
          type="button"
          className="btn btn-secondary"
          onClick={onGenerateNew}
        >
          ? ������� ��� ���������
        </button>
      </div>
    </div>
  );
}
