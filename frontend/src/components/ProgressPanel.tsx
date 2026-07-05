import React, { useState, useEffect, useCallback } from 'react';
import type { GenerationStatus } from '../types';
import { STAGE_LABELS, STAGE_COLORS, STAGE_ORDER } from '../types';

interface ProgressPanelProps {
  status: GenerationStatus;
  onCancel: () => void;
  onRetry: () => void;
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m > 0) {
    return `${m} ��� ${s} ���`;
  }
  return `${s} ���`;
}

function getStageIndex(stage: string): number {
  const idx = STAGE_ORDER.indexOf(stage as any);
  return idx >= 0 ? idx : -1;
}

function getStageLabel(stage: string): string {
  return STAGE_LABELS[stage] || stage;
}

function getStageColor(stage: string): string {
  return STAGE_COLORS[stage] || '#6b7280';
}

export default function ProgressPanel({
  status,
  onCancel,
  onRetry,
}: ProgressPanelProps) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // Timer: ���������� ������ �������
  useEffect(() => {
    if (status.status === 'completed' || status.status === 'failed') {
      // ��� completed/failed � ��������� ��������� �����
      if (status.created_at && status.completed_at) {
        let createdStr = status.created_at;
        let completedStr = status.completed_at;
        if (!createdStr.includes('Z') && !createdStr.includes('+')) createdStr += 'Z';
        if (!completedStr.includes('Z') && !completedStr.includes('+')) completedStr += 'Z';
        const elapsed = Math.floor(
          (new Date(completedStr).getTime() - new Date(createdStr).getTime()) / 1000
        );
        setElapsedSeconds(Math.max(0, elapsed));
      }
      return;
    }

    // �������� ������
    let startTime = Date.now();
    if (status.created_at) {
      let dateStr = status.created_at;
      // If the date string has no timezone info, treat it as UTC
      if (!dateStr.includes('Z') && !dateStr.includes('+') && !dateStr.includes('T00:')) {
        dateStr = dateStr.replace(' ', 'T') + 'Z';
      }
      startTime = new Date(dateStr).getTime();
    }
    setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));

    const interval = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    return () => clearInterval(interval);
  }, [status.created_at, status.completed_at, status.status]);

  const isFailed = status.status === 'failed';
  const isCompleted = status.status === 'completed';
  const isActive = !isFailed && !isCompleted;

  const currentStageIndex = getStageIndex(status.status);
  const progressColor = isFailed ? '#ef4444' : getStageColor(status.status);
  const progressPercent = Math.min(100, Math.max(0, status.stage_progress));

  // ����������� ������� ��� ������� ����� ��������
  const getStageStatus = useCallback(
    (stageIdx: number) => {
      if (isFailed && stageIdx >= currentStageIndex) {
        return 'failed' as const;
      }
      if (stageIdx < currentStageIndex || (isCompleted && stageIdx < STAGE_ORDER.length - 1)) {
        return 'done' as const;
      }
      if (stageIdx === currentStageIndex || (isCompleted && stageIdx === STAGE_ORDER.length - 1)) {
        return 'current' as const;
      }
      return 'pending' as const;
    },
    [currentStageIndex, isCompleted, isFailed]
  );

  return (
    <div className={`card progress-panel ${isFailed ? 'panel-error' : ''}`}>
      <div className="progress-header">
        {isActive && <span className="spinner" />}
        <span className="progress-title">
          {isFailed ? '? ������ ���������' : isCompleted ? '? ��������� ���������' : '? ��������� ����������'}
        </span>
      </div>

      {/* Progress bar */}
      <div className="progress-bar-container">
        <div
          className="progress-bar-fill"
          style={{
            width: `${progressPercent}%`,
            backgroundColor: progressColor,
          }}
        />
        <span className="progress-percent">{progressPercent}%</span>
      </div>

      {/* Current stage info */}
      <div className="progress-stage-info">
        <strong>{getStageLabel(status.status)}</strong>
        {status.status === 'generating' && status.total_sections > 0 && (
          <span className="section-counter">
            {' '}� ������ {status.completed_sections} �� {status.total_sections} ({Math.round(
              (status.completed_sections / status.total_sections) * 100
            )}%)
          </span>
        )}
      </div>

      {/* Timer */}
      <div className="progress-timer">
        <div>? ������: {formatDuration(elapsedSeconds)}</div>
      </div>

      {/* Checklist stages */}
      <div className="stage-checklist">
        <h4>�����:</h4>
        <ul>
          {STAGE_ORDER.map((stage, idx) => {
            const stageStatus = getStageStatus(idx);
            const isLastCompleted = stage === 'completed' && isCompleted;
            const label = getStageLabel(stage);
            let icon = '?';
            let className = 'stage-pending';
            if (stageStatus === 'done' || isLastCompleted) {
              icon = '?';
              className = 'stage-done';
            } else if (stageStatus === 'current') {
              icon = '?';
              className = 'stage-current';
            } else if (stageStatus === 'failed') {
              icon = '?';
              className = 'stage-failed';
            }
            return (
              <li key={stage} className={className}>
                {icon} {label}
                {stageStatus === 'current' && status.status === 'generating' && status.total_sections > 0 && (
                  <span className="stage-detail"> ({status.completed_sections}/{status.total_sections})</span>
                )}
              </li>
            );
          })}
        </ul>
      </div>

      {/* Error message */}
      {isFailed && status.error_message && (
        <div className="error-detail">
          <strong>������:</strong> {status.error_message}
        </div>
      )}

      {/* Actions */}
      <div className="progress-actions">
        {isFailed ? (
          <>
            <button type="button" className="btn btn-primary" onClick={onRetry}>
              ?? Retry
            </button>
            <button type="button" className="btn btn-secondary" onClick={onCancel}>
              ? Cancel
            </button>
          </>
        ) : isCompleted ? null : (
          <button type="button" className="btn btn-cancel" onClick={onCancel}>
            ? ������
          </button>
        )}
      </div>
    </div>
  );
}
