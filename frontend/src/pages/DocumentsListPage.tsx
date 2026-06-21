import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Table,
  Tag,
  Button,
  Input,
  Select,
  Space,
  Typography,
  Alert,
  Empty,
  Card,
  Popconfirm,
  message,
} from 'antd'
import {
  UploadOutlined,
  SearchOutlined,
  FileTextOutlined,
  DownloadOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { DocumentListItem, DocumentStatus } from '../types'
import { useDocumentStore } from '../store/documentStore'
import { useAuthStore } from '../store/authStore'
import { downloadDocumentVersion, deleteDocument } from '../api/documents'
import { STATUS_LABELS, STATUS_COLORS, formatFileSize } from '../utils/statusHelpers'
import dayjs from 'dayjs'

const { Title } = Typography

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: 'all', label: 'Все статусы' },
  ...Object.entries(STATUS_LABELS).map(([value, label]) => ({
    value,
    label,
  })),
]

export default function DocumentsListPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const {
    documents,
    total,
    page,
    pageSize,
    loading,
    error,
    fetchDocuments,
    clearError,
  } = useDocumentStore()

  const [statusFilter, setStatusFilter] = useState<string>(
    searchParams.get('status') || 'all'
  )
  const [searchText, setSearchText] = useState<string>(
    searchParams.get('search') || ''
  )

  const { user } = useAuthStore()
  const isAdmin = user?.companies?.some((h) => h.role === 'admin') ?? false

  const loadDocuments = useCallback(
    (params?: { status?: string; search?: string; page?: number }) => {
      fetchDocuments(params)
    },
    [fetchDocuments]
  )

  useEffect(() => {
    loadDocuments({
      status: statusFilter !== 'all' ? statusFilter : undefined,
      search: searchText || undefined,
      page: 1,
    })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleStatusChange = (value: string) => {
    setStatusFilter(value)
    const params: Record<string, string> = {}
    if (value !== 'all') params.status = value
    if (searchText) params.search = searchText
    setSearchParams(params)
    loadDocuments({
      status: value !== 'all' ? value : undefined,
      search: searchText || undefined,
      page: 1,
    })
  }

  const handleSearch = (value: string) => {
    setSearchText(value)
    const params: Record<string, string> = {}
    if (statusFilter !== 'all') params.status = statusFilter
    if (value) params.search = value
    setSearchParams(params)
    loadDocuments({
      status: statusFilter !== 'all' ? statusFilter : undefined,
      search: value || undefined,
      page: 1,
    })
  }

  const handleTableChange = (pagination: any) => {
    loadDocuments({
      status: statusFilter !== 'all' ? statusFilter : undefined,
      search: searchText || undefined,
      page: pagination.current,
    })
  }

  const columns: ColumnsType<DocumentListItem> = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 70,
      sorter: (a, b) => a.id - b.id,
    },
    {
      title: 'Название',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (text: string) => (
        <Space>
          <FileTextOutlined style={{ color: '#1890ff' }} />
          <span>{text}</span>
        </Space>
      ),
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      width: 150,
      render: (status: DocumentStatus) => (
        <Tag color={STATUS_COLORS[status]}>{STATUS_LABELS[status]}</Tag>
      ),
    },
    {
      title: 'Тип',
      dataIndex: 'file_type',
      key: 'file_type',
      width: 80,
      render: (type: string) => (
        <Tag>{type.toUpperCase()}</Tag>
      ),
    },
    {
      title: 'Размер',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 100,
      render: (size: number) => formatFileSize(size),
    },
    {
      title: 'Версия',
      dataIndex: 'version_number',
      key: 'version_number',
      width: 80,
      align: 'center',
    },
    {
      title: 'Автор',
      dataIndex: ['created_by', 'email'],
      key: 'created_by',
      width: 200,
      ellipsis: true,
    },
    {
      title: 'Дата создания',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (date: string) => dayjs(date).format('DD.MM.YYYY HH:mm'),
      sorter: (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    },
    {
      title: 'Действия',
      key: 'actions',
      width: 120,
      render: (_: any, record: DocumentListItem) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<DownloadOutlined />}
            disabled={!record.current_version}
            onClick={async (e) => {
              e.stopPropagation()
              if (record.current_version) {
                try {
                  const version = record.current_version
                  const ext = version.file_type === 'pdf' ? 'pdf' : 'docx'
                  const filename = `${record.title.replace(/[<>:"/\\|?*]/g, '_')}_v${version.version_number}.${ext}`
                  await downloadDocumentVersion(version.id, filename)
                } catch {
                  message.error('Не удалось скачать документ')
                }
              }
            }}
          >
            Скачать
          </Button>
          {/* Admin delete button — only for admins */}
          {isAdmin && (
            <Popconfirm
              title="Удалить документ?"
              description="Документ будет удалён навсегда со всеми версиями."
              onConfirm={() => handleAdminDelete(record.id)}
              okText="Удалить"
              cancelText="Отмена"
              okButtonProps={{ danger: true }}
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
          )}
        </Space>
      ),
    },
  ]

  const handleAdminDelete = async (id: number) => {
    try {
      await deleteDocument(id)
      message.success('Документ удалён навсегда')
      fetchDocuments()
    } catch {
      message.error('Ошибка при удалении документа')
    }
  }

  return (
    <div style={{ padding: 24 }}>
      <Card>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 24,
          }}
        >
          <Title level={3} style={{ margin: 0 }}>
            Реестр документов
          </Title>
          <Button
            type="primary"
            icon={<UploadOutlined />}
            onClick={() => navigate('/documents/upload')}
          >
            Загрузить документ
          </Button>
        </div>

        {error && (
          <Alert
            message={error}
            type="error"
            showIcon
            closable
            onClose={clearError}
            style={{ marginBottom: 16 }}
          />
        )}

        <Space style={{ marginBottom: 16 }} wrap>
          <Select
            value={statusFilter}
            onChange={handleStatusChange}
            options={STATUS_OPTIONS}
            style={{ width: 180 }}
            aria-label="Фильтр по статусу"
          />
          <Input.Search
            placeholder="Поиск по названию..."
            allowClear
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onSearch={handleSearch}
            prefix={<SearchOutlined />}
            style={{ width: 350 }}
            aria-label="Поиск документов"
          />
        </Space>

        <Table
          columns={columns}
          dataSource={documents}
          rowKey="id"
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: false,
            showTotal: (total) => `Всего: ${total}`,
          }}
          onChange={handleTableChange}
          onRow={(record) => ({
            onClick: () => navigate(`/documents/${record.id}`),
            style: { cursor: 'pointer' },
          })}
          locale={{
            emptyText: (
              <Empty
                description="Документы не найдены"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            ),
          }}
          scroll={{ x: 900 }}
          size="middle"
        />
      </Card>
    </div>
  )
}
