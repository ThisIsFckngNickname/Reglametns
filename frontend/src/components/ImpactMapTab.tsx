import { useEffect, useState, useCallback } from 'react'
import { Table, Tag, Typography, Spin, Empty, Alert, Segmented } from 'antd'
import {
  EditOutlined,
  LinkOutlined,
  SwapOutlined,
  StopOutlined,
  FileSearchOutlined,
  ApartmentOutlined,
  TableOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { ImpactMap, ImpactItem } from '../types'
import { getImpactMap } from '../api/impact'
import ImpactGraph from './ImpactGraph'

const { Title, Text } = Typography

interface ImpactTableItem extends ImpactItem {
  direction: 'incoming' | 'outgoing'
  category: 'orders' | 'documents'
}

const IMPACT_TYPE_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  amends: {
    label: 'Изменяет',
    color: 'blue',
    icon: <EditOutlined />,
  },
  supersedes: {
    label: 'Заменяет',
    color: 'orange',
    icon: <SwapOutlined />,
  },
  references: {
    label: 'Ссылается',
    color: 'green',
    icon: <LinkOutlined />,
  },
  related: {
    label: 'Связан',
    color: 'default',
    icon: <FileSearchOutlined />,
  },
  cancels: {
    label: 'Отменяет',
    color: 'red',
    icon: <StopOutlined />,
  },
}

const columns: ColumnsType<ImpactTableItem> = [
  {
    title: 'Тип связи',
    dataIndex: 'type',
    key: 'type',
    width: 160,
    render: (type: string) => {
      const config = IMPACT_TYPE_CONFIG[type] || { label: type, color: 'default', icon: null }
      return (
        <Tag color={config.color} style={{ fontSize: 13, padding: '2px 10px' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            {config.icon}
            <span>{config.label}</span>
          </span>
        </Tag>
      )
    },
  },
  {
    title: 'Документ / Приказ',
    dataIndex: 'title',
    key: 'title',
    render: (title: string, record: ImpactTableItem) => (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <Tag color={record.category === 'orders' ? 'purple' : 'geekblue'}>
          {record.category === 'orders' ? 'Приказ' : 'Документ'}
        </Tag>
        <Text>{title}</Text>
      </span>
    ),
  },
  {
    title: 'Дата',
    dataIndex: 'date',
    key: 'date',
    width: 130,
    render: (date: string | undefined) =>
      date ? <Text>{date}</Text> : <Text type="secondary">—</Text>,
  },
]

interface ImpactMapTabProps {
  documentId: number
}

type ViewMode = 'table' | 'graph'

export default function ImpactMapTab({ documentId }: ImpactMapTabProps) {
  const [impactMap, setImpactMap] = useState<ImpactMap | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('table')

  const loadImpactMap = useCallback(async () => {
    if (!documentId) return
    setLoading(true)
    setError(null)
    try {
      const data = await getImpactMap(documentId)
      setImpactMap(data)
    } catch (err: any) {
      setError(
        err?.response?.data?.detail?.message || err.message || 'Ошибка загрузки карты влияний'
      )
    } finally {
      setLoading(false)
    }
  }, [documentId])

  useEffect(() => {
    loadImpactMap()
  }, [loadImpactMap])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px 0' }}>
        <Spin size="large" tip="Загрузка карты влияний..." />
      </div>
    )
  }

  if (error) {
    return <Alert message="Ошибка" description={error} type="error" showIcon />
  }

  // Build flat tables for incoming and outgoing
  const incomingItems: ImpactTableItem[] = [
    ...(impactMap?.incoming.orders.map((item) => ({
      ...item,
      direction: 'incoming' as const,
      category: 'orders' as const,
    })) || []),
    ...(impactMap?.incoming.documents.map((item) => ({
      ...item,
      direction: 'incoming' as const,
      category: 'documents' as const,
    })) || []),
  ]

  const outgoingItems: ImpactTableItem[] = [
    ...(impactMap?.outgoing.orders.map((item) => ({
      ...item,
      direction: 'outgoing' as const,
      category: 'orders' as const,
    })) || []),
    ...(impactMap?.outgoing.documents.map((item) => ({
      ...item,
      direction: 'outgoing' as const,
      category: 'documents' as const,
    })) || []),
  ]

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        {impactMap && (
          <Title level={5} style={{ margin: 0 }}>
            Документ: {impactMap.document_title}
          </Title>
        )}

        <Segmented<ViewMode>
          value={viewMode}
          onChange={(val) => setViewMode(val)}
          options={[
            { value: 'table', label: 'Таблица', icon: <TableOutlined /> },
            { value: 'graph', label: 'Граф', icon: <ApartmentOutlined /> },
          ]}
        />
      </div>

      {viewMode === 'graph' ? (
        <ImpactGraph documentId={documentId} />
      ) : (
        <>
          {/* Incoming */}
          <div style={{ marginBottom: 32 }}>
            <Title level={5} style={{ marginBottom: 12 }}>
              Влияющие документы
              <Text type="secondary" style={{ fontWeight: 400, marginLeft: 8 }}>
                ({incomingItems.length})
              </Text>
            </Title>

            {incomingItems.length === 0 ? (
              <Empty
                description="Нет входящих связей"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                style={{ margin: '24px 0' }}
              />
            ) : (
              <Table
                dataSource={incomingItems}
                rowKey={(item, index) => `incoming-${item.id}-${item.category}-${index}`}
                columns={columns}
                pagination={false}
                size="middle"
              />
            )}
          </div>

          {/* Outgoing */}
          <div>
            <Title level={5} style={{ marginBottom: 12 }}>
              Затрагиваемые документы
              <Text type="secondary" style={{ fontWeight: 400, marginLeft: 8 }}>
                ({outgoingItems.length})
              </Text>
            </Title>

            {outgoingItems.length === 0 ? (
              <Empty
                description="Нет исходящих связей"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                style={{ margin: '24px 0' }}
              />
            ) : (
              <Table
                dataSource={outgoingItems}
                rowKey={(item, index) => `outgoing-${item.id}-${item.category}-${index}`}
                columns={columns}
                pagination={false}
                size="middle"
              />
            )}
          </div>
        </>
      )}
    </div>
  )
}
