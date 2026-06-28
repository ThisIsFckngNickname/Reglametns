import { Typography, Space, Button } from 'antd'
import type { DiffStats } from '../types'
import './DiffView.css'

const { Title, Text } = Typography

interface DiffViewProps {
  oldText: string
  newText: string
  htmlDiff: string
  stats: DiffStats
  documentTitle: string
  onClose: () => void
  onApply?: () => void
}

export default function DiffView({
  htmlDiff,
  stats,
  documentTitle,
  onClose,
  onApply,
}: DiffViewProps) {
  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Title level={5} style={{ margin: 0, marginBottom: 8 }}>
          Изменения документа: {documentTitle}
        </Title>
        <Space size="large">
          <Text>
            <span style={{ color: '#52c41a' }}>+{stats.added}</span> добавлено,
            <span style={{ color: '#ff4d4f' }}> −{stats.removed}</span> удалено,
            <span style={{ color: '#faad14' }}> ~{stats.changed}</span> изменено
          </Text>
        </Space>
      </div>

      <div
        className="diff-container"
        style={{
          maxHeight: '60vh',
          overflow: 'auto',
          border: '1px solid #f0f0f0',
          borderRadius: 4,
          background: '#fff',
          padding: 8,
        }}
        dangerouslySetInnerHTML={{ __html: htmlDiff }}
      />

      <div style={{ marginTop: 16, textAlign: 'right' }}>
        <Space>
          {onApply && (
            <Button type="primary" onClick={onApply}>
              Применить
            </Button>
          )}
          <Button onClick={onClose}>Закрыть</Button>
        </Space>
      </div>
    </div>
  )
}
