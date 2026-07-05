import React, { useState, useEffect, useCallback, useRef } from 'react';
import { listProfiles, analyzeProfile, deleteProfile } from '../api/client';
import type { CompanyProfile } from '../types';
import UploadForm from './UploadForm';
import ProfileCard from './ProfileCard';

export default function CompanyProfilePanel() {
  const [profiles, setProfiles] = useState<CompanyProfile[]>([]);
  const [loading, setLoading] = useState(false);
  const [analyzingIds, setAnalyzingIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [uploadNotification, setUploadNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, []);

  const fetchProfiles = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listProfiles();
      setProfiles(data.items);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Ошибка загрузки профилей'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProfiles();
  }, [fetchProfiles]);

  const handleUploadResult = (result: { success: boolean; message: string }) => {
    setUploadNotification({ type: result.success ? 'success' : 'error', message: result.message });
    setTimeout(() => setUploadNotification(null), 6000);
    fetchProfiles();
  };

  const stopPolling = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  const handleAnalyze = async (profileId: string) => {
    stopPolling();
    setAnalyzingIds((prev) => new Set(prev).add(profileId));
    setError(null);
    try {
      await analyzeProfile(profileId);
      pollingRef.current = setInterval(async () => {
        try {
          const data = await listProfiles();
          if (!mountedRef.current) {
            stopPolling();
            return;
          }
          setProfiles(data.items);
          const updated = data.items.find(
            (p) => p.profile_id === profileId
          );
          if (
            updated &&
            (updated.status === 'ready' || updated.status === 'failed')
          ) {
            stopPolling();
            setAnalyzingIds((prev) => {
              const next = new Set(prev);
              next.delete(profileId);
              return next;
            });
          }
        } catch {
          // continue polling silently
        }
      }, 3000);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Ошибка запуска анализа'
      );
      setAnalyzingIds((prev) => {
        const next = new Set(prev);
        next.delete(profileId);
        return next;
      });
    }
  };

  const handleDelete = async (profileId: string) => {
    if (!confirm('Удалить профиль? Все данные будут потеряны.')) return;
    setError(null);
    try {
      await deleteProfile(profileId);
      setProfiles((prev) => prev.filter((p) => p.profile_id !== profileId));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Ошибка удаления'
      );
    }
  };

  return (
    <div className="company-profile-panel">
      <UploadForm onUploadResult={handleUploadResult} />

      {uploadNotification && (
        <div className={`upload-notification ${uploadNotification.type === 'success' ? 'notification-success' : 'notification-error'}`}>
          {uploadNotification.type === 'success' ? '✅ ' : '❌ '}
          {uploadNotification.message}
        </div>
      )}

      {error && <div className="error-message">{error}</div>}

      <div className="panel-section">
        <h2>Профили компании</h2>
        {loading && profiles.length === 0 ? (
          <div className="loading">Загрузка профилей...</div>
        ) : profiles.length === 0 ? (
          <div className="history-empty">
            <p>Нет загруженных профилей</p>
            <p>Загрузите .docx документы для создания профиля</p>
          </div>
        ) : (
          <div className="profile-list">
            {profiles.map((p) => (
              <ProfileCard
                key={p.profile_id}
                profile={p}
                onAnalyze={handleAnalyze}
                onDelete={handleDelete}
                analyzing={analyzingIds.has(p.profile_id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
