import React, { useState, useEffect, useRef } from 'react';
import type { GenerationStatus, DocumentInfo, ProviderInfo } from './types';
import {
  startGeneration,
  pollGenerationStatus,
  getGenerationStatus,
  listDocuments,
  listProviders,
  ApiError,
} from './api/client';
import GeneratorForm from './components/GeneratorForm';
import ProgressPanel from './components/ProgressPanel';
import ResultPanel from './components/ResultPanel';
import HistoryList from './components/HistoryList';
import DocumentAnalysisPanel from './components/DocumentAnalysisPanel';

type TabName = 'generate' | 'documents' | 'history';

function App() {
  // --- ��������� ---
  const [currentGeneration, setCurrentGeneration] = useState<GenerationStatus | null>(null);
  const [history, setHistory] = useState<DocumentInfo[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [isPolling, setIsPolling] = useState(false);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabName>('generate');

  // Refs ��� ���������� polling
  const abortControllerRef = useRef<AbortController | null>(null);

  // --- �������� ��������� ������ ---
  useEffect(() => {
    Promise.all([listDocuments(), listProviders()])
      .then(([docs, provs]) => {
        setHistory(docs);
        setProviders(provs);
      })
      .catch((err) => {
        console.error('Initial load failed:', err);
        setGlobalError('�� ������� ��������� ������. ���������, ��� ������ �������.');
      })
      .finally(() => setIsInitialLoading(false));
  }, []);

  // --- ���������� ������� ��������� ---
  const handleStartGeneration = async (topic: string, provider: string, isMulti: boolean, documentId?: string) => {
    // ������ ����������� polling ���� ���
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    // ������������� placeholder-������
    const placeholderStatus: GenerationStatus = {
      id: 'pending',
      topic,
      status: 'accepted',
      current_stage: '������ � ���������',
      stage_progress: 0,
      total_sections: 0,
      completed_sections: 0,
      provider_used: provider,
      created_at: new Date().toISOString(),
    };
    setCurrentGeneration(placeholderStatus);
    setIsPolling(true);
    setGlobalError(null);

    try {
      if (isMulti) {
        // Multi-stage: POST /api/generate/multi + polling
        const { generation_id } = await startGeneration(topic, provider, documentId);

        // ������ AbortController ��� ����� polling-�����
        const abortController = new AbortController();
        abortControllerRef.current = abortController;

        // ��������� id � currentGeneration
        setCurrentGeneration((prev) =>
          prev ? { ...prev, id: generation_id } : prev
        );

        // Polling � ��������� AbortSignal
        const finalStatus = await pollGenerationStatus(
          generation_id,
          (statusUpdate) => {
            setCurrentGeneration((prev) => ({
              ...(prev || placeholderStatus),
              ...statusUpdate,
              id: generation_id,
              topic,
            }));
          },
          abortController.signal,
          3000,
        );

        // ��������� ���������� �������
        setCurrentGeneration((prev) => ({
          ...(prev || placeholderStatus),
          ...finalStatus,
          id: generation_id,
          topic,
        }));

        // ��������� �������
        try {
          const docs = await listDocuments();
          setHistory(docs);
        } catch {
          // �� ��������
        }
      } else {
        // Single-stage (legacy): POST /api/generate � ����������
        const res = await fetch('/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic, provider }),
        });

        if (!res.ok) {
          const errBody = await res.json().catch(() => null);
          throw new ApiError(
            res.status,
            errBody?.detail || (await res.text())
          );
        }

        const data = await res.json();

        // Single-stage ���������� document_id ��������
        setCurrentGeneration({
          id: 'single-' + Date.now(),
          topic,
          status: 'completed',
          current_stage: '������',
          stage_progress: 100,
          total_sections: data.total_sections || 0,
          completed_sections: data.total_sections || 0,
          provider_used: provider,
          document_id: data.document_id || data.id,
          created_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
        });

        // ��������� �������
        try {
          const docs = await listDocuments();
          setHistory(docs);
        } catch {
          // �� ��������
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        // Polling ��� ������ � �� ���������� ������
        return;
      }

      setCurrentGeneration((prev) =>
        prev
          ? {
              ...prev,
              status: 'failed' as const,
              error_message: err instanceof Error ? err.message : '����������� ������',
            }
          : null
      );
    } finally {
      setIsPolling(false);
      if (abortControllerRef.current) {
        abortControllerRef.current = null;
      }
    }
  };

  // --- ����� (����� ���������) ---
  const handleGenerateNew = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setCurrentGeneration(null);
    setIsPolling(false);
  };

  // --- ������ ---
  if (isInitialLoading) {
    return (
      <div className="app">
        <header>
          <h1>?? ��������� ������������� �����������</h1>
        </header>
        <main>
          <div className="loading">��������...</div>
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <header>
        <h1>?? ��������� ������������� �����������</h1>
      </header>

      <nav className="tabs">
        <button
          type="button"
          className={`tab-button${activeTab === 'generate' ? ' tab-active' : ''}`}
          onClick={() => setActiveTab('generate')}
        >
          ���������
        </button>
        <button
          type="button"
          className={`tab-button${activeTab === 'documents' ? ' tab-active' : ''}`}
          onClick={() => setActiveTab('documents')}
        >
          ������ ����������
        </button>
        <button
          type="button"
          className={`tab-button${activeTab === 'history' ? ' tab-active' : ''}`}
          onClick={() => setActiveTab('history')}
        >
          �������
        </button>
      </nav>

      <main>
        {globalError && (
          <div className="global-error">
            {globalError}
            <button
              type="button"
              className="btn btn-small"
              onClick={() => setGlobalError(null)}
            >
              ?
            </button>
          </div>
        )}

        {activeTab === 'generate' && (
          <>
            <GeneratorForm
              providers={providers}
              disabled={isPolling}
              onStartGeneration={handleStartGeneration}
              onCancelGeneration={handleGenerateNew}
            />

            {/* ProgressPanel: ���������� �� ����� ��������� (����� completed/failed) */}
            {currentGeneration &&
              currentGeneration.status !== 'completed' &&
              currentGeneration.status !== 'failed' && (
                <ProgressPanel
                  status={currentGeneration}
                  onCancel={handleGenerateNew}
                  onRetry={() =>
                    handleStartGeneration(
                      currentGeneration.topic,
                      currentGeneration.provider_used || 'auto',
                      true,
                    )
                  }
                />
              )}

            {/* ProgressPanel � ������ failed (���������� ������) */}
            {currentGeneration?.status === 'failed' && (
              <ProgressPanel
                status={currentGeneration}
                onCancel={handleGenerateNew}
                onRetry={() =>
                  handleStartGeneration(
                    currentGeneration.topic,
                    currentGeneration.provider_used || 'auto',
                    true,
                  )
                }
              />
            )}

            {/* ResultPanel: ���������� ������ ��� complete */}
            {currentGeneration?.status === 'completed' && (
              <ResultPanel
                status={currentGeneration}
                onGenerateNew={handleGenerateNew}
              />
            )}
          </>
        )}

        {activeTab === 'documents' && <DocumentAnalysisPanel />}

        {activeTab === 'history' && (
          <HistoryList
            documents={history}
            onRefresh={() => listDocuments().then(setHistory)}
          />
        )}
      </main>
    </div>
  );
}

export default App;
