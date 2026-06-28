import { useMemo } from 'react'
import { Steps, Alert, Descriptions, Typography, Space } from 'antd'
import {
  FileTextOutlined,
  ApartmentOutlined,
  BookOutlined,
  FontSizeOutlined,
  LinkOutlined,
  ExperimentOutlined,
  DatabaseOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons'
import type { AnalysisStepStatus, AnalysisStatusResponse } from '../types/analysis'

const { Text } = Typography

interface AnalysisPipelineProgressProps {
  stepsStatus: Record<string, AnalysisStepStatus> | null
  status: 'running' | 'complete' | 'error'
  errorMessage?: string | null
  resultSummary?: AnalysisStatusResponse['result_summary'] | null
}

const STEP_DEFINITIONS: { key: string; title: string; icon: React.ReactNode }[] = [
  { key: 'extract_text', title: 'Извлечение текста', icon: <FileTextOutlined /> },
  { key: 'parse_structure', title: 'Парсинг структуры', icon: <ApartmentOutlined /> },
  { key: 'extract_terms', title: 'Термины', icon: <BookOutlined /> },
  { key: 'extract_abbr', title: 'Сокращения', icon: <FontSizeOutlined /> },
  { key: 'extract_refs', title: 'Ссылки', icon: <LinkOutlined /> },
  { key: 'pattern_analysis', title: 'Паттерны', icon: <ExperimentOutlined /> },
  { key: 'embedding', title: 'Индексация (ChromaDB)', icon: <DatabaseOutlined /> },
  { key: 'mark_complete', title: 'Завершение', icon: <CheckCircleOutlined /> },
]

function stepStatusToAntd(status: string | undefined): 'wait' | 'process' | 'finish' | 'error' {
  switch (status) {
    case 'waiting':
      return 'wait'
    case 'running':
      return 'process'
    case 'done':
      return 'finish'
    case 'error':
      return 'error'
    default:
      return 'wait'
  }
}

export default function AnalysisPipelineProgress({
  stepsStatus,
  status,
  errorMessage,
  resultSummary,
}: AnalysisPipelineProgressProps) {
  const stepItems = useMemo(() => {
    return STEP_DEFINITIONS.map((step) => {
      const stepData = stepsStatus ? stepsStatus[step.key] : undefined
      return {
        key: step.key,
        title: step.title,
        status: stepStatusToAntd(stepData?.status),
        icon: step.icon,
        description: stepData?.error || undefined,
      }
    })
  }, [stepsStatus])

  if (!stepsStatus || Object.keys(stepsStatus).length === 0) {
    return (
      <div style={{ padding: '24px 0' }}>
        <Text type="secondary">Нет данных о прогрессе анализа</Text>
      </div>
    )
  }

  return (
    <div>
      <Steps
        current={stepItems.findIndex((s) => s.status === 'process' || s.status === 'error')}
        status={status === 'error' ? 'error' : 'process'}
        direction="vertical"
        size="small"
        items={stepItems}
        style={{ marginBottom: 16 }}
      />

      {status === 'error' && errorMessage && (
        <Alert
          message="Ошибка анализа"
          description={errorMessage}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {resultSummary && (
        <Descriptions
          title="Результаты анализа"
          bordered
          size="small"
          column={{ xs: 1, sm: 2, md: 3 }}
          style={{ marginTop: 16 }}
        >
          {resultSummary.sections_found !== undefined && (
            <Descriptions.Item label="Найдено разделов">
              {resultSummary.sections_found}
            </Descriptions.Item>
          )}
          {resultSummary.terms_found !== undefined && (
            <Descriptions.Item label="Терминов">
              {resultSummary.terms_found}
            </Descriptions.Item>
          )}
          {resultSummary.abbreviations_found !== undefined && (
            <Descriptions.Item label="Сокращений">
              {resultSummary.abbreviations_found}
            </Descriptions.Item>
          )}
          {resultSummary.references_found !== undefined && (
            <Descriptions.Item label="Ссылок">
              {resultSummary.references_found}
            </Descriptions.Item>
          )}
          {resultSummary.chunks_indexed !== undefined && (
            <Descriptions.Item label="Чанков проиндексировано">
              {resultSummary.chunks_indexed}
            </Descriptions.Item>
          )}
          {resultSummary.style_analyzed !== undefined && (
            <Descriptions.Item label="Анализ стиля">
              {resultSummary.style_analyzed ? 'Выполнен' : 'Не выполнен'}
            </Descriptions.Item>
          )}
          {resultSummary.total_steps !== undefined && (
            <Descriptions.Item label="Всего шагов">
              {resultSummary.total_steps}
            </Descriptions.Item>
          )}
          {resultSummary.completed_steps !== undefined && (
            <Descriptions.Item label="Завершено шагов">
              {resultSummary.completed_steps}
            </Descriptions.Item>
          )}
          {resultSummary.failed_steps !== undefined && resultSummary.failed_steps > 0 && (
            <Descriptions.Item label="Шагов с ошибками">
              <Text type="danger">{resultSummary.failed_steps}</Text>
            </Descriptions.Item>
          )}
        </Descriptions>
      )}

      {status === 'complete' && !resultSummary && (
        <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          Анализ завершён. Детальная статистика отсутствует.
        </Text>
      )}
    </div>
  )
}
