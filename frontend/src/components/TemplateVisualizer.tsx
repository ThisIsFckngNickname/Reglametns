import React from 'react';
import type { AnalysisStats } from '../types';

interface TemplateVisualizerProps {
  stats: AnalysisStats;
}

const STAT_CATEGORIES: { key: keyof AnalysisStats; label: string }[] = [
  { key: 'paragraphs_with_role_pct', label: 'Роли' },
  { key: 'paragraphs_with_deadline_pct', label: 'Сроки' },
  { key: 'paragraphs_with_method_pct', label: 'Методы' },
  { key: 'paragraphs_with_condition_pct', label: 'Условия' },
  { key: 'paragraphs_with_document_pct', label: 'Документы' },
  { key: 'paragraphs_with_consequence_pct', label: 'Последствия' },
];

export default function TemplateVisualizer({ stats }: TemplateVisualizerProps) {
  return (
    <div className="visualizer">
      <h4>Статистика заполнения</h4>
      <div className="stats-grid">
        {STAT_CATEGORIES.map((cat) => {
          const raw = stats[cat.key];
          const value = typeof raw === 'number' ? raw : 0;
          return (
            <div key={cat.key} className="stat-item">
              <div className="stat-label">{cat.label}</div>
              <div className="stat-bar">
                <div
                  className="stat-bar-fill"
                  style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
                />
              </div>
              <div className="stat-value">{Math.round(value)}%</div>
            </div>
          );
        })}
      </div>
      <div className="stats-summary">
        <span>Всего параграфов: {stats.total_paragraphs}</span>
        <span>Всего шагов: {stats.total_steps}</span>
        <span>
          Ср. шагов на параграф: {stats.avg_steps_per_paragraph.toFixed(1)}
        </span>
      </div>
    </div>
  );
}
