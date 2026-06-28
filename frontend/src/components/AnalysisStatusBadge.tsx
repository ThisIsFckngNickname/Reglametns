import { Tag } from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  MinusCircleOutlined,
} from '@ant-design/icons'
import type { AnalysisStatus } from '../types/analysis'

interface AnalysisStatusBadgeProps {
  status: AnalysisStatus
}

const STATUS_CONFIG: Record<AnalysisStatus, { color: string; text: string; icon: React.ReactNode }> = {
  none: {
    color: 'default',
    text: 'Не проанализирован',
    icon: <MinusCircleOutlined />,
  },
  running: {
    color: 'processing',
    text: 'Анализ…',
    icon: <LoadingOutlined />,
  },
  complete: {
    color: 'success',
    text: 'Проанализирован',
    icon: <CheckCircleOutlined />,
  },
  error: {
    color: 'error',
    text: 'Ошибка анализа',
    icon: <CloseCircleOutlined />,
  },
}

export default function AnalysisStatusBadge({ status }: AnalysisStatusBadgeProps) {
  const config = STATUS_CONFIG[status]
  return (
    <Tag color={config.color} icon={config.icon}>
      {config.text}
    </Tag>
  )
}
