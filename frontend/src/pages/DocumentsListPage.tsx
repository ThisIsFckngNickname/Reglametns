import { useEffect, useState, useCallback, useRef } from 'react'
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
  Tooltip,
} from 'antd'
import {
  UploadOutlined,
  SearchOutlined,
  FileTextOutlined,
  DownloadOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { DocumentListItem, DocumentStatus } from '../types'
import { useDocumentStore } from '../store/documentStore'
import { useAuthStore } from '../store/authStore'
import { downloadDocumentVersion, deleteDocument, analyzeDocument } from '../api/documents'
import { STATUS_LABELS, STATUS_COLORS, formatFileSize } from '../utils/statusHelpers'
import dayjs from 'dayjs'

const { Title, Text } = Typography

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: 'all', label: 'Все статусы' },
  ...Object.entries(STATUS_LABELS).map(([value, label]) => ({
    value,
    label,
  })),
]

// Resizable column header component
const ResizableTitle = (props: any) => {
  const { onResize, width, children, ...restProps } = props

  const resizableRef = useRef<HTMLDivElement>(null)
  const [resizing, setResizing] = useState(false)
  const startXRef = useRef(0)
  const startWidthRef = useRef(width || 100)

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    startXRef.current = e.clientX
    startWidthRef.current = width || 100
    setResizing(true)

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const diff = moveEvent.clientX - startXRef.current
      const newWidth = Math.max(60, startWidthRef.current + diff)
      onResize(newWidth)
    }

    const handleMouseUp = () => {
      setResizing(false)
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }

  return (
    <th {...restProps} style={{ ...(restProps.style || {}), position: 'relative' }}>
      {children}
      <div
        ref={resizableRef}
        onMouseDown={handleMouseDown}
        style={{
          position: 'absolute',
          right: 0,
          top: 0,
          bottom: 0,
          width: 6,
          cursor: 'col-resize',
          background: resizing ? '#1677ff' : 'transparent',
          opacity: resizing ? 0.8 : 0,
          userSelect: 'none',
          zIndex: 1,
        }}
        onMouseEnter={(e) => { (e.target as HTMLElement).style.opacity = '0.4' }}
        onMouseLeave={(e) => { if (!resizing) (e.target as HTMLElement).style.opacity = '0' }}
      />
    </th>
  )
}

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
  const [selectedRowIds, setSelectedRowIds] = useState<number[]>([])
  const [analyzingIds, setAnalyzingIds] = useState<Set<number>>(new Set())

  const [columnWidths, setColumnWidths] = useState<Record<string, number>>({
    id: 70,
    title: 350,
    status: 150,
    file_type: 80,
    file_size: 100,
    version_number: 80,
    created_by: 200,
    created_at: 170,
    actions: 120,
  })

  const updateColumnWidth = useCallback((key: string, width: number) => {
    setColumnWidths(prev => ({ ...prev, [key]: width }))
  }, [])

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
      width: columnWidths.id,
      onHeaderCell: () => ({
        width: columnWidths.id,
        onResize: (w: number) => updateColumnWidth('id', w),
      }),
      sorter: (a, b) => a.id - b.id,
    },
    {
      title: 'Название',
      dataIndex: 'title',
      key: 'title',
      width: columnWidths.title,
      ellipsis: true,
      onHeaderCell: () => ({
        width: columnWidths.title,
        onResize: (w: number) => updateColumnWidth('title', w),
      }),
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
      width: columnWidths.status,
      onHeaderCell: () => ({
        width: columnWidths.status,
        onResize: (w: number) => updateColumnWidth('status', w),
      }),
      render: (status: DocumentStatus) => (
        <Tag color={STATUS_COLORS[status]}>{STATUS_LABELS[status]}</Tag>
      ),
    },
    {
      title: 'Тип',
      dataIndex: 'file_type',
      key: 'file_type',
      width: columnWidths.file_type,
      onHeaderCell: () => ({
        width: columnWidths.file_type,
        onResize: (w: number) => updateColumnWidth('file_type', w),
      }),
      render: (type: string) => (
        <Tag>{type.toUpperCase()}</Tag>
      ),
    },
    {
      title: 'Размер',
      dataIndex: 'file_size',
      key: 'file_size',
      width: columnWidths.file_size,
      onHeaderCell: () => ({
        width: columnWidths.file_size,
        onResize: (w: number) => updateColumnWidth('file_size', w),
      }),
      render: (size: number) => formatFileSize(size),
    },
    {
      title: 'Версия',
      dataIndex: 'version_number',
      key: 'version_number',
      width: columnWidths.version_number,
      align: 'center',
      onHeaderCell: () => ({
        width: columnWidths.version_number,
        onResize: (w: number) => updateColumnWidth('version_number', w),
      }),
    },
    {
      title: 'Автор',
      dataIndex: ['created_by', 'email'],
      key: 'created_by',
      width: columnWidths.created_by,
      ellipsis: true,
      onHeaderCell: () => ({
        width: columnWidths.created_by,
        onResize: (w: number) => updateColumnWidth('created_by', w),
      }),
    },
    {
      title: 'Дата создания',
      dataIndex: 'created_at',
      key: 'created_at',
      width: columnWidths.created_at,
      onHeaderCell: () => ({
        width: columnWidths.created_at,
        onResize: (w: number) => updateColumnWidth('created_at', w),
      }),
      render: (date: string) => dayjs(date).format('DD.MM.YYYY HH:mm'),
      sorter: (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    },
    {
      title: 'Анализ',
      key: 'analysis',
      width: 110,
      align: 'center',
      render: (_: any, record: DocumentListItem) => {
        const isAnalyzing = analyzingIds.has(record.id)
        return (
          <Tooltip title={record.was_analyzed ? 'Повторный анализ' : 'Запустить анализ'}>
            <Button
              type={record.was_analyzed ? 'default' : 'primary'}
              size="small"
              loading={isAnalyzing}
              icon={record.was_analyzed ? <CheckCircleOutlined /> : undefined}
              onClick={(e) => {
                e.stopPropagation()
                handleAnalyzeSingle(record.id)
              }}
              style={{ minWidth: 90 }}
            >
              {isAnalyzing ? '' : record.was_analyzed ? 'Готово' : 'Анализ'}
            </Button>
          </Tooltip>
        )
      },
    },
    {
      title: 'Действия',
      key: 'actions',
      width: columnWidths.actions,
      onHeaderCell: () => ({
        width: columnWidths.actions,
        onResize: (w: number) => updateColumnWidth('actions', w),
      }),
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

  const handleAnalyzeSingle = async (id: number) => {
    setAnalyzingIds(prev => new Set(prev).add(id))
    try {
      await analyzeDocument(id)
      message.success('Документ проанализирован')
      fetchDocuments()
    } catch (err: any) {
      const msg = err?.response?.data?.detail?.message || err?.message || 'Ошибка анализа'
      message.error(msg)
    } finally {
      setAnalyzingIds(prev => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
  }

  const handleAnalyzeSelected = async () => {
    if (selectedRowIds.length === 0) {
      message.warning('Выберите документы для анализа')
      return
    }
    
    const idsToAnalyze = selectedRowIds
    setSelectedRowIds([]) // Clear selection
    
    let successCount = 0
    let failCount = 0
    
    for (const id of idsToAnalyze) {
      setAnalyzingIds(prev => new Set(prev).add(id))
      try {
        await analyzeDocument(id)
        successCount++
      } catch {
        failCount++
      } finally {
        setAnalyzingIds(prev => {
          const next = new Set(prev)
          next.delete(id)
          return next
        })
      }
    }
    
    const parts = []
    if (successCount > 0) parts.push(`${successCount} успешно`)
    if (failCount > 0) parts.push(`${failCount} с ошибкой`)
    
    message.success(`Анализ завершён: ${parts.join(', ')}`)
    fetchDocuments()
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

        {selectedRowIds.length > 0 && (
          <div
            style={{
              marginBottom: 16,
              padding: '8px 16px',
              background: '#e6f4ff',
              borderRadius: 6,
              border: '1px solid #91caff',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <Text>
              Выбрано документов: <Text strong>{selectedRowIds.length}</Text>
            </Text>
            <Space>
              <Button
                type="primary"
                onClick={handleAnalyzeSelected}
                loading={analyzingIds.size > 0}
              >
                Анализировать выбранные ({selectedRowIds.length})
              </Button>
              <Button onClick={() => setSelectedRowIds([])}>
                Снять выделение
              </Button>
            </Space>
          </div>
        )}

        <Table
          columns={columns}
          dataSource={documents}
          rowKey="id"
          loading={loading}
          rowSelection={{
            selectedRowKeys: selectedRowIds,
            onChange: (selectedRowKeys) => setSelectedRowIds(selectedRowKeys as number[]),
            preserveSelectedRowKeys: false,
          }}
          components={{
            header: {
              cell: ResizableTitle,
            },
          }}
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
