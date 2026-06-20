import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Descriptions,
  Tag,
  Button,
  Typography,
  Spin,
  Alert,
  Card,
  Table,
  Modal,
  Select,
  Empty,
  Space,
  Breadcrumb,
  Popconfirm,
  message,
} from 'antd'
import {
  ArrowLeftOutlined,
  DownloadOutlined,
  DeleteOutlined,
  LinkOutlined,
  FileTextOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { Order, OrderDocumentLink, OrderStatus, DocumentListItem } from '../types'
import { getOrder, cancelOrder, getOrderDocuments, linkOrderToDocument, unlinkOrderFromDocument } from '../api/orders'
import { getDocuments } from '../api/documents'
import { formatFileSize } from '../utils/statusHelpers'
import dayjs from 'dayjs'

const { Title, Text } = Typography

const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  draft: 'Черновик',
  active: 'Действующий',
  cancelled: 'Отменён',
}

const ORDER_STATUS_COLORS: Record<OrderStatus, string> = {
  draft: 'orange',
  active: 'green',
  cancelled: 'default',
}

const LINK_TYPE_LABELS: Record<string, string> = {
  approves: 'Утверждает',
  amends: 'Изменяет',
  references: 'Ссылается',
  related: 'Связан',
}

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const orderId = parseInt(id || '0')

  const [order, setOrder] = useState<Order | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [documents, setDocuments] = useState<OrderDocumentLink[]>([])
  const [documentsLoading, setDocumentsLoading] = useState(false)

  const [linkModalOpen, setLinkModalOpen] = useState(false)
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null)
  const [selectedLinkType, setSelectedLinkType] = useState<string>('references')
  const [linkDescription, setLinkDescription] = useState<string>('')
  const [linking, setLinking] = useState(false)

  const [docList, setDocList] = useState<DocumentListItem[]>([])
  const [docSearch, setDocSearch] = useState('')

  const [cancelling, setCancelling] = useState(false)

  const loadOrder = useCallback(async () => {
    if (!orderId) return
    setLoading(true)
    setError(null)
    try {
      const data = await getOrder(orderId)
      setOrder(data)
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail?.message ||
        err?.message ||
        'Ошибка загрузки приказа'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [orderId])

  const loadDocuments = useCallback(async () => {
    if (!orderId) return
    setDocumentsLoading(true)
    try {
      const data = await getOrderDocuments(orderId)
      setDocuments(data.items)
    } catch {
      // Silently fail
    } finally {
      setDocumentsLoading(false)
    }
  }, [orderId])

  useEffect(() => {
    loadOrder()
    loadDocuments()
  }, [loadOrder, loadDocuments])

  // Load document list for linking
  const loadDocList = useCallback(async () => {
    try {
      const data = await getDocuments({ page: 1, page_size: 50 })
      setDocList(data.items)
    } catch {
      // Silently fail
    }
  }, [])

  const handleOpenLinkModal = () => {
    loadDocList()
    setSelectedDocId(null)
    setSelectedLinkType('references')
    setLinkDescription('')
    setLinkModalOpen(true)
  }

  const handleLinkDocument = async () => {
    if (!selectedDocId) {
      message.error('Выберите документ')
      return
    }
    setLinking(true)
    try {
      await linkOrderToDocument(
        orderId,
        selectedDocId,
        selectedLinkType,
        linkDescription || undefined
      )
      message.success('Документ привязан к приказу')
      setLinkModalOpen(false)
      loadDocuments()
    } catch {
      message.error('Ошибка при привязке документа')
    } finally {
      setLinking(false)
    }
  }

  const handleUnlinkDocument = async (linkId: number) => {
    try {
      await unlinkOrderFromDocument(orderId, linkId)
      message.success('Связь удалена')
      loadDocuments()
    } catch {
      message.error('Ошибка при удалении связи')
    }
  }

  const handleCancelOrder = async () => {
    if (!order) return
    setCancelling(true)
    try {
      await cancelOrder(order.id)
      message.success('Приказ отменён')
      loadOrder()
    } catch {
      message.error('Ошибка при отмене приказа')
    } finally {
      setCancelling(false)
    }
  }

  const handleDownload = () => {
    // In a real app, this would download the file
    message.info('Скачивание файла (заглушка)')
  }

  // Loading state
  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <Spin size="large" tip="Загрузка приказа..." />
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div style={{ padding: 24 }}>
        <Button
          type="link"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/orders')}
          style={{ padding: 0, marginBottom: 16 }}
        >
          Назад к реестру приказов
        </Button>
        <Alert
          message="Ошибка загрузки приказа"
          description={error}
          type="error"
          showIcon
        />
      </div>
    )
  }

  // Not found
  if (!order) {
    return (
      <div style={{ padding: 24 }}>
        <Button
          type="link"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/orders')}
          style={{ padding: 0, marginBottom: 16 }}
        >
          Назад к реестру приказов
        </Button>
        <Empty description="Приказ не найден" />
      </div>
    )
  }

  const docColumns: ColumnsType<OrderDocumentLink> = [
    {
      title: 'Документ',
      dataIndex: ['document', 'title'],
      key: 'title',
      ellipsis: true,
    },
    {
      title: 'Тип связи',
      dataIndex: 'link_type',
      key: 'link_type',
      width: 140,
      render: (t: string) => (
        <Tag>{LINK_TYPE_LABELS[t] || t}</Tag>
      ),
    },
    {
      title: 'Описание',
      dataIndex: 'description',
      key: 'description',
      width: 200,
      render: (val: string | null) => val || '—',
    },
    {
      title: 'Действия',
      key: 'actions',
      width: 100,
      render: (_: any, record: OrderDocumentLink) => (
        <Popconfirm
          title="Удалить связь?"
          onConfirm={() => handleUnlinkDocument(record.id)}
          okText="Удалить"
          cancelText="Отмена"
        >
          <Button
            type="link"
            danger
            size="small"
            icon={<DeleteOutlined />}
          >
            Удалить
          </Button>
        </Popconfirm>
      ),
    },
  ]

  // Filter docs already linked
  const linkedDocIds = documents.map((d) => d.document_id)
  const availableDocs = docList.filter((d) => !linkedDocIds.includes(d.id))

  return (
    <div style={{ padding: 24 }}>
      <Breadcrumb
        items={[
          {
            title: (
              <span
                onClick={() => navigate('/orders')}
                style={{ cursor: 'pointer' }}
              >
                Приказы
              </span>
            ),
          },
          {
            title: order.title,
          },
        ]}
        style={{ marginBottom: 16 }}
      />

      <Button
        type="link"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/orders')}
        style={{ padding: 0, marginBottom: 16 }}
      >
        Назад к реестру приказов
      </Button>

      {/* Title and actions */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 24,
        }}
      >
        <Space align="center">
          <FileTextOutlined style={{ fontSize: 24, color: '#1890ff' }} />
          <div>
            <Title level={3} style={{ margin: 0 }}>
              {order.title}
            </Title>
            <Space style={{ marginTop: 4 }}>
              <Tag color={ORDER_STATUS_COLORS[order.status]}>
                {ORDER_STATUS_LABELS[order.status]}
              </Tag>
              {order.order_number && (
                <Text type="secondary">
                  № {order.order_number}
                </Text>
              )}
            </Space>
          </div>
        </Space>

        <Space>
          {order.file_type && (
            <Button
              icon={<DownloadOutlined />}
              onClick={handleDownload}
            >
              Скачать
            </Button>
          )}

          {order.status !== 'cancelled' && (
            <Popconfirm
              title="Отменить приказ?"
              description="Приказ будет переведён в статус «Отменён»."
              onConfirm={handleCancelOrder}
              okText="Отменить"
              cancelText="Отмена"
              okButtonProps={{ danger: true }}
            >
              <Button
                icon={<DeleteOutlined />}
                danger
                loading={cancelling}
              >
                Архивировать
              </Button>
            </Popconfirm>
          )}
        </Space>
      </div>

      {/* Details */}
      <Card title="Детали приказа" style={{ marginBottom: 24 }}>
        <Descriptions bordered column={{ xs: 1, sm: 2 }} size="small">
          <Descriptions.Item label="Номер">
            {order.order_number || '—'}
          </Descriptions.Item>
          <Descriptions.Item label="Дата">
            {order.order_date
              ? dayjs(order.order_date).format('DD.MM.YYYY')
              : '—'}
          </Descriptions.Item>
          <Descriptions.Item label="Название" span={2}>
            {order.title}
          </Descriptions.Item>
          <Descriptions.Item label="Описание" span={2}>
            {order.description || <Text type="secondary">Нет описания</Text>}
          </Descriptions.Item>
          <Descriptions.Item label="Статус">
            <Tag color={ORDER_STATUS_COLORS[order.status]}>
              {ORDER_STATUS_LABELS[order.status]}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Тип файла">
            {order.file_type ? (
              <Tag>{order.file_type.toUpperCase()}</Tag>
            ) : (
              '—'
            )}
          </Descriptions.Item>
          <Descriptions.Item label="Размер файла">
            {order.file_size != null
              ? formatFileSize(order.file_size)
              : '—'}
          </Descriptions.Item>
          <Descriptions.Item label="Автор">
            {order.created_by.email}
          </Descriptions.Item>
          <Descriptions.Item label="Дата создания">
            {dayjs(order.created_at).format('DD.MM.YYYY HH:mm')}
          </Descriptions.Item>
          <Descriptions.Item label="Дата обновления">
            {dayjs(order.updated_at).format('DD.MM.YYYY HH:mm')}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* Linked Documents */}
      <Card
        title="Связанные документы"
        extra={
          order.status !== 'cancelled' && (
            <Button
              type="primary"
              icon={<LinkOutlined />}
              onClick={handleOpenLinkModal}
            >
              Привязать документ
            </Button>
          )
        }
      >
        {documentsLoading ? (
          <div style={{ textAlign: 'center', padding: 24 }}>
            <Spin />
          </div>
        ) : documents.length === 0 ? (
          <Empty
            description="Нет связанных документов"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        ) : (
          <Table
            dataSource={documents}
            rowKey="id"
            columns={docColumns}
            pagination={false}
            size="middle"
          />
        )}
      </Card>

      {/* Link Document Modal */}
      <Modal
        title="Привязать документ"
        open={linkModalOpen}
        onOk={handleLinkDocument}
        onCancel={() => setLinkModalOpen(false)}
        confirmLoading={linking}
        okText="Привязать"
        cancelText="Отмена"
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Text strong>Документ</Text>
            <Select
              showSearch
              style={{ width: '100%', marginTop: 4 }}
              placeholder="Найдите и выберите документ"
              value={selectedDocId}
              onChange={setSelectedDocId}
              onSearch={setDocSearch}
              filterOption={(input, option) =>
                (option?.label as string || '')
                  .toLowerCase()
                  .includes(input.toLowerCase())
              }
              options={availableDocs.map((d) => ({
                value: d.id,
                label: `${d.title} (v${d.version_number})`,
              }))}
              notFoundContent={
                <Empty
                  description="Документы не найдены"
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                />
              }
            />
          </div>

          <div>
            <Text strong>Тип связи</Text>
            <Select
              style={{ width: '100%', marginTop: 4 }}
              value={selectedLinkType}
              onChange={setSelectedLinkType}
              options={[
                { value: 'approves', label: 'Утверждает' },
                { value: 'amends', label: 'Изменяет' },
                { value: 'references', label: 'Ссылается' },
                { value: 'related', label: 'Связан' },
              ]}
            />
          </div>
        </Space>
      </Modal>
    </div>
  )
}
