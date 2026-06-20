import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Table,
  Button,
  Select,
  Tag,
  Typography,
  Spin,
  Empty,
  Space,
  Breadcrumb,
} from 'antd'
import {
  PlusOutlined,
  FileTextOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { Order, OrderStatus } from '../types'
import { getOrders } from '../api/orders'
import { formatFileSize } from '../utils/statusHelpers'
import dayjs from 'dayjs'

const { Title } = Typography

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

export default function OrdersListPage() {
  const navigate = useNavigate()
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(false)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(10)

  const loadOrders = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, any> = { page, page_size: pageSize }
      if (statusFilter && statusFilter !== 'all') {
        params.status = statusFilter
      }
      const data = await getOrders(params)
      setOrders(data.items)
      setTotal(data.total)
    } catch {
      // Silently fail
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, statusFilter])

  useEffect(() => {
    loadOrders()
  }, [loadOrders])

  useEffect(() => {
    setPage(1)
  }, [statusFilter])

  const columns: ColumnsType<Order> = [
    {
      title: 'Номер',
      dataIndex: 'order_number',
      key: 'order_number',
      width: 130,
      render: (val: string | null) => val || '—',
    },
    {
      title: 'Название',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
    },
    {
      title: 'Дата',
      dataIndex: 'order_date',
      key: 'order_date',
      width: 120,
      render: (val: string | null) =>
        val ? dayjs(val).format('DD.MM.YYYY') : '—',
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      width: 140,
      render: (status: OrderStatus) => (
        <Tag color={ORDER_STATUS_COLORS[status]}>
          {ORDER_STATUS_LABELS[status]}
        </Tag>
      ),
    },
    {
      title: 'Тип файла',
      dataIndex: 'file_type',
      key: 'file_type',
      width: 100,
      render: (val: string | null) =>
        val ? <Tag>{val.toUpperCase()}</Tag> : '—',
    },
    {
      title: 'Размер',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 100,
      render: (val: number | null) =>
        val != null ? formatFileSize(val) : '—',
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <Breadcrumb
        items={[{ title: 'Приказы' }]}
        style={{ marginBottom: 16 }}
      />

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
        }}
      >
        <Space align="center">
          <FileTextOutlined style={{ fontSize: 24, color: '#1890ff' }} />
          <Title level={3} style={{ margin: 0 }}>
            Реестр приказов
          </Title>
        </Space>

        <Space>
          <Select
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { value: 'all', label: 'Все статусы' },
              { value: 'active', label: 'Действующие' },
              { value: 'draft', label: 'Черновики' },
              { value: 'cancelled', label: 'Отменённые' },
            ]}
            style={{ width: 180 }}
            aria-label="Фильтр по статусу"
          />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate('/orders/upload')}
          >
            Загрузить приказ
          </Button>
        </Space>
      </div>

      {loading ? (
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '40vh',
          }}
        >
          <Spin size="large" tip="Загрузка приказов..." />
        </div>
      ) : orders.length === 0 ? (
        <Empty
          description="Приказы не найдены"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Button
            type="primary"
            onClick={() => navigate('/orders/upload')}
          >
            Загрузить первый приказ
          </Button>
        </Empty>
      ) : (
        <Table
          dataSource={orders}
          rowKey="id"
          columns={columns}
          pagination={{
            current: page,
            pageSize,
            total,
            onChange: (p) => setPage(p),
            showTotal: (t) => `Всего: ${t}`,
          }}
          size="middle"
          onRow={(record) => ({
            onClick: () => navigate(`/orders/${record.id}`),
            style: { cursor: 'pointer' },
          })}
        />
      )}
    </div>
  )
}
