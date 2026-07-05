import React, { useState } from 'react';
import type { CompanyProfile } from '../types';
import { getProfileDownloadUrl } from '../api/client';
import TemplateVisualizer from './TemplateVisualizer';
import StepInspector from './StepInspector';

interface ProfileCardProps {
  profile: CompanyProfile;
  onAnalyze: (profileId: string) => void;
  onDelete: (profileId: string) => void;
  analyzing: boolean;
}

export default function ProfileCard({
  profile,
  onAnalyze,
  onDelete,
  analyzing,
}: ProfileCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="card profile-card">
      <div className="profile-card-header">
        <div className="profile-title-row">
          <h3 className="profile-name">{profile.name}</h3>
          <span className={`profile-status status-${profile.status}`}>
            {profile.status}
          </span>
        </div>
        <div className="profile-doc-count">
          Документов: {profile.document_count}
        </div>
      </div>

      {(analyzing || profile.status === 'extracting' ||
        profile.status === 'analyzing' ||
        profile.status === 'synthesizing') && (
        <div className="profile-progress">
          {/* Animated progress bar */}
          <div className="progress-bar-container">
            <div
              className={`progress-bar-fill progress-animated`}
              style={{
                width: `${Math.max(profile.progress_pct, 5)}%`,
                backgroundColor: profile.status === 'extracting' ? '#f59e0b' :
                                profile.status === 'analyzing' ? '#3b82f6' :
                                profile.status === 'synthesizing' ? '#8b5cf6' :
                                '#2563eb',
              }}
            />
            <span className="progress-percent">{profile.progress_pct}%</span>
          </div>

          {/* Pipeline stage indicators */}
          <div className="pipeline-stages">
            {['extracting', 'analyzing', 'synthesizing'].map((stage) => {
              const effectiveStatus = analyzing && profile.status === 'uploaded' ? 'extracting' : profile.status;
              const currentIndex = ['extracting', 'analyzing', 'synthesizing'].indexOf(effectiveStatus);
              const stageIndex = ['extracting', 'analyzing', 'synthesizing'].indexOf(stage);
              const stageLabels: Record<string, string> = {
                extracting: '📄 Извлечение',
                analyzing: '🔍 Анализ',
                synthesizing: '🧠 Синтез',
              };
              const isActive = effectiveStatus === stage;
              const isDone = currentIndex > stageIndex;
              return (
                <div key={stage} className={`pipeline-stage ${isActive ? 'active' : ''} ${isDone ? 'done' : ''} ${!isActive && !isDone ? 'pending' : ''}`}>
                  <div className={`pipeline-dot ${isActive ? 'pulse' : ''}`}>
                    {isDone ? '✓' : isActive ? '◉' : '○'}
                  </div>
                  <span className="pipeline-label">{stageLabels[stage]}</span>
                </div>
              );
            })}
          </div>

          {/* Detailed progress info from analysis_stats */}
          {profile.analysis_stats && (
            <div className="progress-details">
              {(profile.analysis_stats as any).batch != null && (profile.analysis_stats as any).total_batches != null && (
                <div className="progress-detail-row">
                  <span className="detail-label">Батч:</span>
                  <span className="detail-value">{(profile.analysis_stats as any).batch}/{(profile.analysis_stats as any).total_batches}</span>
                </div>
              )}
              {(profile.analysis_stats as any).paragraphs_processed != null && (profile.analysis_stats as any).total_paragraphs != null && (
                <div className="progress-detail-row">
                  <span className="detail-label">Параграфы:</span>
                  <span className="detail-value">{(profile.analysis_stats as any).paragraphs_processed}/{(profile.analysis_stats as any).total_paragraphs}</span>
                </div>
              )}
              {(profile.analysis_stats as any).detail && (
                <div className="progress-detail-row">
                  <span className="detail-label">Статус:</span>
                  <span className="detail-value">{(profile.analysis_stats as any).detail}</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div className="profile-actions">
        {profile.status === 'uploaded' && (
          <button
            type="button"
            className="btn btn-primary btn-small"
            onClick={() => onAnalyze(profile.profile_id)}
            disabled={analyzing}
          >
            {analyzing ? 'Анализ...' : 'Анализировать'}
          </button>
        )}
        <button
          type="button"
          className="btn btn-cancel btn-small"
          onClick={() => onDelete(profile.profile_id)}
        >
          Удалить
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-small"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? 'Свернуть' : 'Подробнее'}
        </button>
      </div>

      {profile.documents && profile.documents.length > 0 && expanded && (
        <div className="document-list">
          <h4>Документы</h4>
          {profile.documents.map((doc) => (
            <div key={doc.id} className="document-item">
              <span className="doc-name">{doc.original_name}</span>
              <span className="document-meta">
                {doc.paragraph_count} параграфов
              </span>
              <a
                href={getProfileDownloadUrl(profile.profile_id, doc.id)}
                className="btn-download"
                download
              >
                ⬇
              </a>
            </div>
          ))}
        </div>
      )}

      {profile.status === 'ready' && profile.analysis_stats && expanded && (
        <TemplateVisualizer stats={profile.analysis_stats} />
      )}

      {profile.status === 'ready' &&
        expanded &&
        profile.documents &&
        profile.documents.length > 0 && (
          <StepInspector
            profileId={profile.profile_id}
            documents={profile.documents}
          />
        )}
    </div>
  );
}
