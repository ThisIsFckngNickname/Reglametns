import React from 'react';
import type { DocumentInfo } from '../types';
import { formatProviderName } from '../types';
import { getDocumentDownloadUrl } from '../api/client';

interface HistoryListProps {
  documents: DocumentInfo[];
  onRefresh: () => void;
}

function formatDate(isoString: string): string {
  try {
    const d = new Date(isoString);
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year = d.getFullYear();
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    return `${day}.${month}.${year} ${hours}:${minutes}`;
  } catch {
    return isoString;
  }
}

function truncateTopic(topic: string, maxLen: number = 50): string {
  if (topic.length <= maxLen) return topic;
  return topic.slice(0, maxLen) + '…';
}

export default function HistoryList({
  documents,
  onRefresh,
}: HistoryListProps) {
  if (documents.length === 0) {
    return (
      <div className="card history-list">
        <div className="history-header">
          <h2>📋 История генераций</h2>
        </div>
        <div className="history-empty">
          <p>Пока нет созданных регламентов.</p>
          <p>Создайте первый регламент выше.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card history-list">
      <div className="history-header">
        <h2>📋 История генераций</h2>
        <button
          type="button"
          className="btn btn-small"
          onClick={onRefresh}
          title="Обновить список"
        >
          🔄
        </button>
      </div>

      <div className="history-table-wrapper">
        <table className="history-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Тема</th>
              <th>Провайдер</th>
              <th>Дата</th>
              <th>Действие</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc, index) => (
              <tr key={doc.id} className={index === 0 ? 'row-first' : ''}>
                <td className="col-num">{index + 1}</td>
                <td className="col-topic" title={doc.topic}>
                  {truncateTopic(doc.topic)}
                </td>
                <td className="col-provider">
                  {formatProviderName(doc.provider_used)}
                </td>
                <td className="col-date">{formatDate(doc.created_at)}</td>
                <td className="col-action">
                  <a
                    href={getDocumentDownloadUrl(doc.id)}
                    className="btn btn-small btn-download"
                    download
                    title="Скачать"
                  >
                    ⬇
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
