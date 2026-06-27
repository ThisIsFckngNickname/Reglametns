import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Tabs,
  Descriptions,
  Tag,
  Button,
  Typography,
  Spin,
  Alert,
  Card,
  Tree,
  Table,
  Select,
  Popconfirm,
  Space,
  Breadcrumb,
  Empty,
  List,
  Modal,
  Upload,
  Input,
  message,
} from 'antd'
import {
  ArrowLeftOutlined,
  DownloadOutlined,
  DeleteOutlined,
  FileTextOutlined,
  FolderOutlined,
  PlusOutlined,
  InboxOutlined,
} from '@ant-design/icons'
import type { DataNode } from 'antd/es/tree'
import type { ColumnsType } from 'antd/es/table'
import type { UploadFile } from 'antd/es/upload'
import type {
  DocumentDetail,
  DocumentSection,
  DocumentTerm,
  DocumentAbbreviation,
  DocumentTable,
  DocumentVersion,
  DocumentStatus,
  DocumentListItem,
  DocumentLink,
} from '../types'
import { useDocumentStore } from '../store/documentStore'
import { useAuthStore } from '../store/authStore'
import {
  getDocuments,
  getDocumentSections,
  getDocumentTerms,
  getDocumentAbbreviations,
  getDocumentTables,
  getDocumentVersions,
  getDownloadUrl,
  downloadDocumentVersion,
  deleteDocument,
  analyzeDocument,
  getDocumentLinks,
  getIncomingLinks,
  createDocumentLink,
  deleteDocumentLink,
} from '../api/documents'
import { createDocumentVersion } from '../api/versions'
import { STATUS_LABELS, STATUS_COLORS, formatFileSize } from '../utils/statusHelpers'
import dayjs from 'dayjs'

const { Title, Text, Paragraph } = Typography
const { TextArea } = Input
const { Dragger } = Upload

// Convert sections tree to Ant Design Tree nodes
function sectionsToTreeNodes(sections: DocumentSection[]): DataNode[] {
  return sections.map((s) => {
    const children = Array.isArray(s.children) ? s.children : []
    return {
      key: `section-${s.id}`,
      title: s.title,
      children: children.length > 0 ? sectionsToTreeNodes(children) : undefined,
      isLeaf: children.length === 0,
    }
  })
}

// Find a section by id in the tree
function findSectionById(sections: DocumentSection[], id: number): DocumentSection | null {
  for (const s of sections) {
    if (s.id === id) return s
    const children = Array.isArray(s.children) ? s.children : []
    if (children.length > 0) {
      const found = findSectionById(children, id)
      if (found) return found
    }
  }
  return null
}

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const documentId = parseInt(id || '0')

  const {
    currentDocument,
    detailLoading,
    detailError,
    fetchDocument,
    updateDocument,
    archiveDocument,
    clearCurrent,
  } = useDocumentStore()

  const [sections, setSections] = useState<DocumentSection[]>([])
  const [sectionsLoading, setSectionsLoading] = useState(false)
  const [selectedSection, setSelectedSection] = useState<DocumentSection | null>(null)

  const [terms, setTerms] = useState<DocumentTerm[]>([])
  const [termsLoading, setTermsLoading] = useState(false)

  const [abbreviations, setAbbreviations] = useState<DocumentAbbreviation[]>([])
  const [abbreviationsLoading, setAbbreviationsLoading] = useState(false)

  const [tables, setTables] = useState<DocumentTable[]>([])
  const [tablesLoading, setTablesLoading] = useState(false)

  const [versions, setVersions] = useState<DocumentVersion[]>([])
  const [versionsLoading, setVersionsLoading] = useState(false)

  const [statusUpdating, setStatusUpdating] = useState(false)

  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeResult, setAnalyzeResult] = useState<string | null>(null)

  const [links, setLinks] = useState<DocumentLink[]>([])
  const [incomingLinks, setIncomingLinks] = useState<DocumentLink[]>([])
  const [linksLoading, setLinksLoading] = useState(false)

  const [linkModalOpen, setLinkModalOpen] = useState(false)
  const [newLinkTargetId, setNewLinkTargetId] = useState<number | undefined>(undefined)
  const [newLinkType, setNewLinkType] = useState<'references' | 'amends' | 'supersedes' | 'related'>('references')
  const [newLinkDescription, setNewLinkDescription] = useState('')
  const [linkCreating, setLinkCreating] = useState(false)
  const [linkSearchText, setLinkSearchText] = useState('')
  const [linkSearchResults, setLinkSearchResults] = useState<DocumentListItem[]>([])
  const [linkSearchLoading, setLinkSearchLoading] = useState(false)

  const { user } = useAuthStore()
  const isAdmin = user?.companies?.some((h) => h.role === 'admin') ?? false

  // ---- Version creation ----
  const [versionModalOpen, setVersionModalOpen] = useState(false)
  const [versionFileList, setVersionFileList] = useState<UploadFile[]>([])
  const [versionNotes, setVersionNotes] = useState('')
  const [versionCreating, setVersionCreating] = useState(false)

  // Load document
  useEffect(() => {
    if (documentId > 0) {
      fetchDocument(documentId)
    }
    return () => {
      clearCurrent()
    }
  }, [documentId, fetchDocument, clearCurrent])

  // Load sections
  const loadSections = useCallback(async () => {
    if (!documentId) return
    setSectionsLoading(true)
    try {
      const data = await getDocumentSections(documentId)
      // Normalize sections: ensure all children are arrays
      const normalizeChildren = (sections: DocumentSection[]): DocumentSection[] => {
        return sections.map(s => ({
          ...s,
          children: Array.isArray(s.children) ? normalizeChildren(s.children) : []
        }))
      }
      setSections(normalizeChildren(data.sections))
    } catch {
      message.error('Не удалось загрузить структуру документа')
    } finally {
      setSectionsLoading(false)
    }
  }, [documentId])

  // Load terms
  const loadTerms = useCallback(async () => {
    if (!documentId) return
    setTermsLoading(true)
    try {
      const data = await getDocumentTerms(documentId)
      setTerms(data.terms)
    } catch {
      // Silently fail
    } finally {
      setTermsLoading(false)
    }
  }, [documentId])

  // Load abbreviations
  const loadAbbreviations = useCallback(async () => {
    if (!documentId) return
    setAbbreviationsLoading(true)
    try {
      const data = await getDocumentAbbreviations(documentId)
      setAbbreviations(data.abbreviations)
    } catch {
      // Silently fail
    } finally {
      setAbbreviationsLoading(false)
    }
  }, [documentId])

  // Load tables
  const loadTables = useCallback(async () => {
    if (!documentId) return
    setTablesLoading(true)
    try {
      const data = await getDocumentTables(documentId)
      setTables(data.tables)
    } catch {
      // Silently fail
    } finally {
      setTablesLoading(false)
    }
  }, [documentId])

  // Load versions
  const loadVersions = useCallback(async () => {
    if (!documentId) return
    setVersionsLoading(true)
    try {
      const data = await getDocumentVersions(documentId)
      setVersions(data.items)
    } catch {
      // Silently fail
    } finally {
      setVersionsLoading(false)
    }
  }, [documentId])

  // Load links
  const loadLinks = useCallback(async () => {
    if (!documentId) return
    setLinksLoading(true)
    try {
      const [outgoing, incoming] = await Promise.all([
        getDocumentLinks(documentId),
        getIncomingLinks(documentId),
      ])
      setLinks(outgoing)
      setIncomingLinks(incoming)
    } catch {
      // Silent fail
    } finally {
      setLinksLoading(false)
    }
  }, [documentId])

  const searchDocumentsForLink = useCallback(async (search: string) => {
    if (!search || search.length < 2) {
      setLinkSearchResults([])
      return
    }
    setLinkSearchLoading(true)
    try {
      const result = await getDocuments({ search, page_size: 20 })
      const filtered = (result.items || []).filter(d => d.id !== documentId)
      setLinkSearchResults(filtered)
    } catch {
      setLinkSearchResults([])
    } finally {
      setLinkSearchLoading(false)
    }
  }, [documentId])

  const handleTabChange = (activeKey: string) => {
    switch (activeKey) {
      case 'structure':
        if (sections.length === 0) loadSections()
        break
      case 'terms':
        if (terms.length === 0) loadTerms()
        break
      case 'abbreviations':
        if (abbreviations.length === 0) loadAbbreviations()
        break
      case 'tables':
        if (tables.length === 0) loadTables()
        break
      case 'versions':
        if (versions.length === 0) loadVersions()
        break
      case 'links':
        if (links.length === 0 && incomingLinks.length === 0) loadLinks()
        break
    }
  }

  const handleStatusChange = async (newStatus: DocumentStatus) => {
    if (!currentDocument) return
    setStatusUpdating(true)
    try {
      await updateDocument(currentDocument.id, { status: newStatus })
      message.success(`Статус изменён на «${STATUS_LABELS[newStatus]}»`)
    } catch {
      message.error('Ошибка при изменении статуса')
    } finally {
      setStatusUpdating(false)
    }
  }

  const handleArchive = async () => {
    if (!currentDocument) return
    try {
      await archiveDocument(currentDocument.id)
      message.success('Документ архивирован')
      navigate('/documents')
    } catch {
      message.error('Ошибка при архивировании документа')
    }
  }

  const handleAdminDelete = async () => {
    if (!currentDocument) return
    try {
      await deleteDocument(currentDocument.id)
      message.success('Документ удалён навсегда')
      navigate('/documents')
    } catch {
      message.error('Ошибка при удалении документа')
    }
  }

  const handleDownload = useCallback(async (versionId: number) => {
    try {
      // Build filename from doc info if available
      const doc = currentDocument
      let filename: string | undefined
      if (doc?.current_version && doc?.title) {
        const version = doc.current_version
        const ext = version.file_type === 'pdf' ? 'pdf' : 'docx'
        filename = `${doc.title.replace(/[<>:"/\\|?*]/g, '_')}_v${version.version_number}.${ext}`
      }
      await downloadDocumentVersion(versionId, filename)
    } catch {
      message.error('Не удалось скачать документ')
    }
  }, [currentDocument])

  const handleAnalyze = async () => {
    if (!currentDocument) return
    setAnalyzing(true)
    setAnalyzeResult(null)
    try {
      const result = await analyzeDocument(currentDocument.id)
      setAnalyzeResult(result.message)
      message.success('Анализ документа завершён')
      fetchDocument(documentId) // Refresh to update was_analyzed
    } catch (err: any) {
      const msg = err?.response?.data?.detail?.message || err?.message || 'Ошибка анализа'
      setAnalyzeResult(msg)
      message.error(msg)
    } finally {
      setAnalyzing(false)
    }
  }

  const handleCreateLink = async () => {
    if (!currentDocument || !newLinkTargetId) {
      message.error('Выберите документ для связи')
      return
    }
    setLinkCreating(true)
    try {
      await createDocumentLink(currentDocument.id, {
        target_document_id: newLinkTargetId,
        link_type: newLinkType,
        description: newLinkDescription || undefined,
      })
      message.success('Связь создана')
      setLinkModalOpen(false)
      setNewLinkTargetId(undefined)
      setNewLinkDescription('')
      loadLinks()
    } catch (err: any) {
      const msg = err?.response?.data?.detail?.message || err?.message || 'Ошибка создания связи'
      message.error(msg)
    } finally {
      setLinkCreating(false)
    }
  }

  const handleDeleteLink = async (linkId: number) => {
    if (!currentDocument) return
    try {
      await deleteDocumentLink(currentDocument.id, linkId)
      message.success('Связь удалена')
      loadLinks()
    } catch {
      message.error('Ошибка удаления связи')
    }
  }

  const handleTreeSelect = (selectedKeys: React.Key[]) => {
    if (selectedKeys.length === 0) {
      setSelectedSection(null)
      return
    }
    const key = selectedKeys[0] as string
    const sectionId = parseInt(key.replace('section-', ''))
    const section = findSectionById(sections, sectionId)
    setSelectedSection(section || null)
  }

  // ---- Version creation handlers ----
  const handleOpenVersionModal = () => {
    setVersionFileList([])
    setVersionNotes('')
    setVersionModalOpen(true)
  }

  const handleCreateVersion = async () => {
    if (versionFileList.length === 0) {
      message.error('Выберите файл для новой версии')
      return
    }
    const file = versionFileList[0].originFileObj
    if (!file) {
      message.error('Файл не найден')
      return
    }

    setVersionCreating(true)
    try {
      await createDocumentVersion(
        documentId,
        file,
        versionNotes || undefined
      )
      message.success('Новая версия создана')
      setVersionModalOpen(false)
      // Reload versions and document
      loadVersions()
      fetchDocument(documentId)
    } catch {
      message.error('Ошибка при создании версии')
    } finally {
      setVersionCreating(false)
    }
  }

  // Loading state
  if (detailLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <Spin size="large" tip="Загрузка документа..." />
      </div>
    )
  }

  // Error state
  if (detailError) {
    return (
      <div style={{ padding: 24 }}>
        <Button
          type="link"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/documents')}
          style={{ padding: 0, marginBottom: 16 }}
        >
          Назад к реестру
        </Button>
        <Alert
          message="Ошибка загрузки документа"
          description={detailError}
          type="error"
          showIcon
        />
      </div>
    )
  }

  // Not found
  if (!currentDocument) {
    return (
      <div style={{ padding: 24 }}>
        <Button
          type="link"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/documents')}
          style={{ padding: 0, marginBottom: 16 }}
        >
          Назад к реестру
        </Button>
        <Empty description="Документ не найден" />
      </div>
    )
  }

  const doc = currentDocument

  // Status options (disallow current status)
  const statusOptions = (Object.keys(STATUS_LABELS) as DocumentStatus[])
    .filter((s) => s !== 'archived') // Can't change from archived
    .map((s) => ({
      value: s,
      label: STATUS_LABELS[s],
      disabled: s === doc.status,
    }))

  // Columns for versions table
  const versionColumns: ColumnsType<DocumentVersion> = [
    {
      title: 'Версия',
      dataIndex: 'version_number',
      key: 'version_number',
      width: 80,
      render: (v: number) => <Tag>v{v}</Tag>,
    },
    {
      title: 'Тип',
      dataIndex: 'file_type',
      key: 'file_type',
      width: 80,
      render: (t: string) => <Tag>{t.toUpperCase()}</Tag>,
    },
    {
      title: 'Размер',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 100,
      render: (s: number) => formatFileSize(s),
    },
    {
      title: 'Комментарий',
      dataIndex: 'version_notes',
      key: 'version_notes',
      ellipsis: true,
      render: (val: string | null) => val || <Text type="secondary">—</Text>,
    },
    {
      title: 'Загрузил',
      dataIndex: ['uploaded_by', 'email'],
      key: 'uploaded_by',
      width: 200,
    },
    {
      title: 'Дата',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (date: string) => dayjs(date).format('DD.MM.YYYY HH:mm'),
    },
    {
      title: 'Действия',
      key: 'actions',
      width: 100,
      render: (_: any, record: DocumentVersion) => (
        <Button
          type="primary"
          size="small"
          icon={<DownloadOutlined />}
          onClick={() => handleDownload(record.id)}
        >
          Скачать
        </Button>
      ),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      {/* Breadcrumbs */}
      <Breadcrumb
        items={[
          {
            title: (
              <span
                onClick={() => navigate('/documents')}
                style={{ cursor: 'pointer' }}
              >
                Реестр документов
              </span>
            ),
          },
          {
            title: doc.title,
          },
        ]}
        style={{ marginBottom: 16 }}
      />

      {/* Back button */}
      <Button
        type="link"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/documents')}
        style={{ padding: 0, marginBottom: 16 }}
      >
        Назад к реестру
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
              {doc.title}
            </Title>
            <Space style={{ marginTop: 4 }}>
              <Tag color={STATUS_COLORS[doc.status]}>
                {STATUS_LABELS[doc.status]}
              </Tag>
              {doc.current_version && (
                <Text type="secondary">
                  v{doc.current_version.version_number}
                </Text>
              )}
            </Space>
          </div>
        </Space>

        <Space>
          {/* Download button — always visible, disabled if no version */}
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            disabled={!doc.current_version}
            onClick={() => doc.current_version && handleDownload(doc.current_version.id)}
          >
            Скачать
          </Button>

          {/* Only show status change for non-archived documents */}
          {doc.status !== 'archived' && (
            <Select
              value={doc.status}
              onChange={handleStatusChange}
              options={statusOptions}
              style={{ width: 180 }}
              loading={statusUpdating}
              aria-label="Изменить статус"
            />
          )}

          {/* Admin delete button */}
          {isAdmin && (
            <Popconfirm
              title="Удалить документ навсегда?"
              description="Это действие необратимо. Все версии, термины и связи будут удалены."
              onConfirm={handleAdminDelete}
              okText="Удалить"
              cancelText="Отмена"
              okButtonProps={{ danger: true }}
            >
              <Button danger icon={<DeleteOutlined />}>
                Удалить навсегда
              </Button>
            </Popconfirm>
          )}

          {doc.status !== 'archived' && (
            <Popconfirm
              title="Архивировать документ?"
              description="Документ будет перемещён в архив. Вы сможете просматривать его, но не сможете изменять."
              onConfirm={handleArchive}
              okText="Архивировать"
              cancelText="Отмена"
            >
              <Button icon={<DeleteOutlined />} danger>
                Архивировать
              </Button>
            </Popconfirm>
          )}
        </Space>
      </div>

      {/* Tabs */}
      <Card>
        <Tabs
          defaultActiveKey="info"
          onChange={handleTabChange}
          items={[
            {
              key: 'info',
              label: 'Информация',
              children: (
                <div>
                  <Descriptions
                    bordered
                    column={{ xs: 1, sm: 2 }}
                    size="small"
                  >
                    <Descriptions.Item label="Название">
                      {doc.title}
                    </Descriptions.Item>
                    <Descriptions.Item label="Статус">
                      <Tag color={STATUS_COLORS[doc.status]}>
                        {STATUS_LABELS[doc.status]}
                      </Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="Описание" span={2}>
                      {doc.description || <Text type="secondary">Нет описания</Text>}
                    </Descriptions.Item>
                    <Descriptions.Item label="Автор">
                      {doc.created_by.email}
                    </Descriptions.Item>
                    <Descriptions.Item label="Текущая версия">
                      {doc.current_version
                        ? `v${doc.current_version.version_number} (${formatFileSize(doc.current_version.file_size)})`
                        : 'Нет версий'}
                    </Descriptions.Item>
                    <Descriptions.Item label="Дата создания">
                      {dayjs(doc.created_at).format('DD.MM.YYYY HH:mm')}
                    </Descriptions.Item>
                    <Descriptions.Item label="Дата обновления">
                      {dayjs(doc.updated_at).format('DD.MM.YYYY HH:mm')}
                    </Descriptions.Item>
                  </Descriptions>

                  <Title level={5} style={{ marginTop: 24, marginBottom: 16 }}>
                    Статистика документа
                  </Title>
                  <Descriptions bordered column={{ xs: 2, sm: 5 }} size="small">
                    <Descriptions.Item label="Разделы">
                      {doc.stats.sections_count}
                    </Descriptions.Item>
                    <Descriptions.Item label="Таблицы">
                      {doc.stats.tables_count}
                    </Descriptions.Item>
                    <Descriptions.Item label="Термины">
                      {doc.stats.terms_count}
                    </Descriptions.Item>
                    <Descriptions.Item label="Сокращения">
                      {doc.stats.abbreviations_count}
                    </Descriptions.Item>
                    <Descriptions.Item label="Версии">
                      {doc.stats.versions_count}
                    </Descriptions.Item>
                  </Descriptions>
                </div>
              ),
            },
            {
              key: 'structure',
              label: `Структура (${doc.stats.sections_count})`,
              children: (
                <div style={{ display: 'flex', gap: 24, minHeight: 400 }}>
                  <div style={{ width: 350, flexShrink: 0, overflow: 'auto' }}>
                    {sectionsLoading ? (
                      <Spin style={{ display: 'block', margin: '40px auto' }} />
                    ) : sections.length === 0 ? (
                      <Empty description="Нет разделов" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    ) : (
                      <Tree
                        treeData={sectionsToTreeNodes(sections)}
                        defaultExpandAll
                        onSelect={handleTreeSelect}
                        showIcon
                        icon={<FolderOutlined />}
                      />
                    )}
                  </div>
                  <div style={{ flex: 1, borderLeft: '1px solid #f0f0f0', paddingLeft: 24 }}>
                    {selectedSection ? (
                      <div>
                        <Title level={5}>{selectedSection.title}</Title>
                        {selectedSection.content ? (
                          <Paragraph
                            style={{
                              whiteSpace: 'pre-wrap',
                              background: '#fafafa',
                              padding: 16,
                              borderRadius: 4,
                            }}
                          >
                            {selectedSection.content}
                          </Paragraph>
                        ) : (
                          <Text type="secondary">Нет содержимого</Text>
                        )}
                      </div>
                    ) : (
                      <Empty
                        description="Выберите раздел в дереве слева"
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                      />
                    )}
                  </div>
                </div>
              ),
            },
            {
              key: 'terms',
              label: `Термины (${doc.stats.terms_count})`,
              children: (
                <div>
                  {termsLoading ? (
                    <Spin style={{ display: 'block', margin: '40px auto' }} />
                  ) : terms.length === 0 ? (
                    <Empty description="Термины не найдены" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    <Table
                      dataSource={terms}
                      rowKey="id"
                      columns={[
                        { title: 'Термин', dataIndex: 'term', key: 'term', width: 250 },
                        { title: 'Определение', dataIndex: 'definition', key: 'definition' },
                      ]}
                      pagination={false}
                      size="middle"
                    />
                  )}
                </div>
              ),
            },
            {
              key: 'abbreviations',
              label: `Сокращения (${doc.stats.abbreviations_count})`,
              children: (
                <div>
                  {abbreviationsLoading ? (
                    <Spin style={{ display: 'block', margin: '40px auto' }} />
                  ) : abbreviations.length === 0 ? (
                    <Empty description="Сокращения не найдены" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    <Table
                      dataSource={abbreviations}
                      rowKey="id"
                      columns={[
                        {
                          title: 'Сокращение',
                          dataIndex: 'abbreviation',
                          key: 'abbreviation',
                          width: 200,
                          render: (text: string) => <Tag>{text}</Tag>,
                        },
                        {
                          title: 'Расшифровка',
                          dataIndex: 'full_form',
                          key: 'full_form',
                        },
                      ]}
                      pagination={false}
                      size="middle"
                    />
                  )}
                </div>
              ),
            },
            {
              key: 'tables',
              label: `Таблицы (${doc.stats.tables_count})`,
              children: (
                <div>
                  {tablesLoading ? (
                    <Spin style={{ display: 'block', margin: '40px auto' }} />
                  ) : tables.length === 0 ? (
                    <Empty description="Таблицы не найдены" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    <List
                      dataSource={tables}
                      renderItem={(table) => (
                        <List.Item>
                          <Card
                            title={
                              table.caption || `Таблица ${table.order_num}`
                            }
                            size="small"
                            style={{ width: '100%' }}
                          >
                            {table.section_title && (
                              <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                                Раздел: {table.section_title}
                              </Text>
                            )}
                            <div
                              dangerouslySetInnerHTML={{ __html: table.html_content }}
                              style={{ overflowX: 'auto' }}
                            />
                            <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
                              {table.rows_count} строк × {table.cols_count} столбцов
                            </Text>
                          </Card>
                        </List.Item>
                      )}
                    />
                  )}
                </div>
              ),
            },
            {
              key: 'versions',
              label: `Версии (${doc.stats.versions_count})`,
              children: (
                <div>
                  <div style={{ marginBottom: 16, textAlign: 'right' }}>
                    {doc.status !== 'archived' && (
                      <Button
                        type="primary"
                        icon={<PlusOutlined />}
                        onClick={handleOpenVersionModal}
                      >
                        Создать версию
                      </Button>
                    )}
                  </div>

                  {versionsLoading ? (
                    <Spin style={{ display: 'block', margin: '40px auto' }} />
                  ) : versions.length === 0 ? (
                    <Empty description="Нет версий" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    <Table
                      dataSource={versions}
                      rowKey="id"
                      columns={versionColumns}
                      pagination={false}
                      size="middle"
                    />
                  )}
                </div>
              ),
            },
            {
              key: 'links',
              label: `Связи (${(links.length + incomingLinks.length) || 0})`,
              children: (
                <div>
                  {/* Links section */}
                  {linksLoading ? (
                    <Spin style={{ display: 'block', margin: '40px auto' }} />
                  ) : (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                        <Title level={5} style={{ margin: 0 }}>Исходящие связи</Title>
                        <Button
                          type="primary"
                          size="small"
                          icon={<PlusOutlined />}
                          onClick={() => setLinkModalOpen(true)}
                        >
                          Добавить связь
                        </Button>
                      </div>

                      {links.length === 0 ? (
                        <Empty description="Нет исходящих связей" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                      ) : (
                        <Table
                          dataSource={links}
                          rowKey="id"
                          pagination={false}
                          size="small"
                          style={{ marginBottom: 24 }}
                          columns={[
                            {
                              title: 'Тип',
                              dataIndex: 'link_type',
                              key: 'link_type',
                              width: 140,
                              render: (type: string) => {
                                const labels: Record<string, string> = {
                                  references: 'Ссылается',
                                  amends: 'Изменяет',
                                  supersedes: 'Заменяет',
                                  related: 'Связан',
                                }
                                return <Tag>{labels[type] || type}</Tag>
                              },
                            },
                            {
                              title: 'Документ',
                              dataIndex: 'target_title',
                              key: 'target_title',
                              ellipsis: true,
                            },
                            {
                              title: 'Статус',
                              dataIndex: 'target_status',
                              key: 'target_status',
                              width: 120,
                              render: (status: string) => (
                                <Tag color={STATUS_COLORS[status as DocumentStatus]}>
                                  {STATUS_LABELS[status as DocumentStatus] || status}
                                </Tag>
                              ),
                            },
                            {
                              title: 'Описание',
                              dataIndex: 'description',
                              key: 'description',
                              ellipsis: true,
                              render: (val: string | null) => val || <Text type="secondary">—</Text>,
                            },
                            {
                              title: '',
                              key: 'actions',
                              width: 60,
                              render: (_: any, record: DocumentLink) => (
                                <Popconfirm
                                  title="Удалить связь?"
                                  onConfirm={() => handleDeleteLink(record.id)}
                                  okText="Да"
                                  cancelText="Нет"
                                >
                                  <Button type="link" danger size="small" icon={<DeleteOutlined />} />
                                </Popconfirm>
                              ),
                            },
                          ]}
                        />
                      )}

                      <Title level={5} style={{ marginTop: 24 }}>Входящие связи</Title>
                      {incomingLinks.length === 0 ? (
                        <Empty description="Нет входящих связей" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                      ) : (
                        <Table
                          dataSource={incomingLinks}
                          rowKey="id"
                          pagination={false}
                          size="small"
                          columns={[
                            {
                              title: 'Тип',
                              dataIndex: 'link_type',
                              key: 'link_type',
                              width: 140,
                              render: (type: string) => {
                                const labels: Record<string, string> = {
                                  references: 'Ссылается',
                                  amends: 'Изменяет',
                                  supersedes: 'Заменяет',
                                  related: 'Связан',
                                }
                                return <Tag>{labels[type] || type}</Tag>
                              },
                            },
                            {
                              title: 'От документа',
                              dataIndex: 'source_title',
                              key: 'source_title',
                              ellipsis: true,
                            },
                            {
                              title: 'Статус',
                              dataIndex: 'source_status',
                              key: 'source_status',
                              width: 120,
                              render: (status: string) => (
                                <Tag color={STATUS_COLORS[status as DocumentStatus]}>
                                  {STATUS_LABELS[status as DocumentStatus] || status}
                                </Tag>
                              ),
                            },
                            {
                              title: 'Описание',
                              dataIndex: 'description',
                              key: 'description',
                              ellipsis: true,
                              render: (val: string | null) => val || <Text type="secondary">—</Text>,
                            },
                          ]}
                        />
                      )}
                    </>
                  )}

                  {/* Create Link Modal */}
                  <Modal
                    title="Добавить связь"
                    open={linkModalOpen}
                    onOk={handleCreateLink}
                    onCancel={() => {
                      setLinkModalOpen(false)
                      setNewLinkTargetId(undefined)
                      setNewLinkDescription('')
                      setLinkSearchText('')
                      setLinkSearchResults([])
                    }}
                    confirmLoading={linkCreating}
                    okText="Создать"
                    cancelText="Отмена"
                    width={520}
                  >
                    <Space direction="vertical" style={{ width: '100%' }} size="middle">
                      <div>
                        <Text strong>Тип связи</Text>
                        <Select
                          value={newLinkType}
                          onChange={setNewLinkType}
                          style={{ width: '100%', marginTop: 4 }}
                          options={[
                            { value: 'references', label: 'Ссылается на' },
                            { value: 'amends', label: 'Изменяет' },
                            { value: 'supersedes', label: 'Заменяет' },
                            { value: 'related', label: 'Связан с' },
                          ]}
                        />
                      </div>
                      <div>
                        <Text strong>Целевой документ</Text>
                        <Select
                          showSearch
                          value={newLinkTargetId}
                          placeholder="Начните вводить название документа..."
                          notFoundContent={
                            linkSearchLoading ? <Spin size="small" /> :
                            linkSearchText.length < 2 ? 'Введите минимум 2 символа' :
                            'Документы не найдены'
                          }
                          filterOption={false}
                          onSearch={(value) => {
                            setLinkSearchText(value)
                            searchDocumentsForLink(value)
                          }}
                          onChange={(value) => setNewLinkTargetId(value)}
                          style={{ width: '100%', marginTop: 4 }}
                          loading={linkSearchLoading}
                        >
                          {linkSearchResults.map((doc) => (
                            <Select.Option key={doc.id} value={doc.id}>
                              <Space>
                                <Tag color={STATUS_COLORS[doc.status]} style={{ marginRight: 4 }}>
                                  #{doc.id}
                                </Tag>
                                <span>{doc.title}</span>
                                <Tag color={STATUS_COLORS[doc.status]}>{STATUS_LABELS[doc.status]}</Tag>
                                <Text type="secondary" style={{ fontSize: 12 }}>
                                  {doc.file_type?.toUpperCase()} v{doc.version_number}
                                </Text>
                              </Space>
                            </Select.Option>
                          ))}
                        </Select>
                        {newLinkTargetId && (
                          <div style={{ marginTop: 4 }}>
                            <Text type="success">
                              ✓ Выбран: {linkSearchResults.find(d => d.id === newLinkTargetId)?.title || `ID=${newLinkTargetId}`}
                            </Text>
                          </div>
                        )}
                      </div>
                      <div>
                        <Text strong>Описание (опционально)</Text>
                        <Input.TextArea
                          rows={2}
                          placeholder="Например: «Использует терминологию из документа»"
                          value={newLinkDescription}
                          onChange={(e) => setNewLinkDescription(e.target.value)}
                          style={{ marginTop: 4 }}
                        />
                      </div>
                    </Space>
                  </Modal>
                </div>
              ),
            },
          ]}
        />
      </Card>

      {/* Create Version Modal */}
      <Modal
        title="Создать новую версию"
        open={versionModalOpen}
        onOk={handleCreateVersion}
        onCancel={() => setVersionModalOpen(false)}
        confirmLoading={versionCreating}
        okText="Создать"
        cancelText="Отмена"
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Text strong>Файл документа</Text>
            <Dragger
              multiple={false}
              accept=".docx,.pdf"
              fileList={versionFileList}
              onRemove={() => setVersionFileList([])}
              beforeUpload={(file) => {
                const isValid =
                  file.type === 'application/pdf' ||
                  file.name.endsWith('.docx') ||
                  file.name.endsWith('.pdf')
                if (!isValid) {
                  message.error('Допустимы только файлы DOCX и PDF')
                  return Upload.LIST_IGNORE
                }
                setVersionFileList([file as UploadFile])
                return false
              }}
              style={{ marginTop: 4 }}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">
                Нажмите или перетащите файл сюда
              </p>
              <p className="ant-upload-hint">
                DOCX или PDF
              </p>
            </Dragger>
          </div>

          <div>
            <Text strong>Комментарий к версии</Text>
            <TextArea
              rows={3}
              value={versionNotes}
              onChange={(e) => setVersionNotes(e.target.value)}
              placeholder="Что изменилось в этой версии (необязательно)"
              style={{ marginTop: 4 }}
            />
          </div>
        </Space>
      </Modal>

    </div>
  )
}
