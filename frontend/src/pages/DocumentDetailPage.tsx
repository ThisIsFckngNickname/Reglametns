import { useEffect, useState, useCallback, useRef } from 'react'
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
  Input,
  message,
  Timeline,
  Checkbox,
  Tooltip,
} from 'antd'
import {
  ArrowLeftOutlined,
  DownloadOutlined,
  DeleteOutlined,
  FileTextOutlined,
  FolderOutlined,
  PlusOutlined,
  ReloadOutlined,
  EditOutlined,
  UploadOutlined,
  RestOutlined,
  DiffOutlined,
} from '@ant-design/icons'
import type { DataNode } from 'antd/es/tree'
import type { ColumnsType } from 'antd/es/table'
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
  VersionItem,
} from '../types'
import type {
  AnalysisStepStatus,
  AnalysisStatusResponse,
  AnalysisHistoryItem,
  AnalysisStatus,
} from '../types/analysis'
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
  downloadVersion,
  deleteDocument,
  analyzeDocument,
  getDocumentLinks,
  getIncomingLinks,
  createDocumentLink,
  deleteDocumentLink,
  getDocumentHistory,
  getDocumentAmendments,
  getDocumentAmendedDocuments,
  restoreVersion,
  compareVersions,
} from '../api/documents'
import type { StatusHistoryItem } from '../api/documents'
import type { AmendmentItem, ReviseResponse, RevisionHistoryItem, RevisionDetail, DiffResult } from '../types'
import {
  getAnalysisHistory,
  getAnalysisStatus,
  reanalyzeDocument,
} from '../api/analysis'
import VersionUploadModal from '../components/VersionUploadModal'
import { reviseDocument, getDocumentRevisions, getDocumentRevisionDetail } from '../api/documents'
import AnalysisStatusBadge from '../components/AnalysisStatusBadge'
import AnalysisPipelineProgress from '../components/AnalysisPipelineProgress'
import ReviseModal from '../components/ReviseModal'
import DiffView from '../components/DiffView'
import type { DocumentType } from '../types/companyTerms'
import { DOCUMENT_TYPE_LABELS } from '../types/companyTerms'
import { STATUS_LABELS, STATUS_COLORS, formatFileSize } from '../utils/statusHelpers'
import dayjs from 'dayjs'

const { Title, Text, Paragraph } = Typography

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

  const [versions, setVersions] = useState<VersionItem[]>([])
  const [versionsLoading, setVersionsLoading] = useState(false)

  const [statusUpdating, setStatusUpdating] = useState(false)

  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeResult, setAnalyzeResult] = useState<string | null>(null)

  const [links, setLinks] = useState<DocumentLink[]>([])
  const [incomingLinks, setIncomingLinks] = useState<DocumentLink[]>([])
  const [linksLoading, setLinksLoading] = useState(false)

  const [amendments, setAmendments] = useState<AmendmentItem[]>([])
  const [amendedDocuments, setAmendedDocuments] = useState<AmendmentItem[]>([])
  const [amendmentsLoading, setAmendmentsLoading] = useState(false)

  const [statusHistory, setStatusHistory] = useState<StatusHistoryItem[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)

  const [linkModalOpen, setLinkModalOpen] = useState(false)
  const [newLinkTargetId, setNewLinkTargetId] = useState<number | undefined>(undefined)
  const [newLinkType, setNewLinkType] = useState<'references' | 'amends' | 'supersedes' | 'related'>('references')
  const [newLinkDescription, setNewLinkDescription] = useState('')
  const [linkCreating, setLinkCreating] = useState(false)
  const [linkSearchText, setLinkSearchText] = useState('')
  const [linkSearchResults, setLinkSearchResults] = useState<DocumentListItem[]>([])
  const [linkSearchLoading, setLinkSearchLoading] = useState(false)
  const searchTimerRef = useRef<ReturnType<typeof setTimeout>>()

  // Analysis state
  const [analysisHistory, setAnalysisHistory] = useState<AnalysisHistoryItem[]>([])
  const [analysisHistoryLoading, setAnalysisHistoryLoading] = useState(false)
  const [selectedAnalysis, setSelectedAnalysis] = useState<AnalysisStatusResponse | null>(null)
  const [selectedAnalysisLoading, setSelectedAnalysisLoading] = useState(false)
  const [reanalyzing, setReanalyzing] = useState(false)
  const pollTimerRef = useRef<ReturnType<typeof setInterval>>()

  // ---- Revision state ----
  const [reviseModalVisible, setReviseModalVisible] = useState(false)
  const [diffResult, setDiffResult] = useState<ReviseResponse | null>(null)
  const [diffVisible, setDiffVisible] = useState(false)
  const [revisions, setRevisions] = useState<RevisionHistoryItem[]>([])
  const [revisionsLoading, setRevisionsLoading] = useState(false)
  const [revisionDetailModalVisible, setRevisionDetailModalVisible] = useState(false)
  const [revisionDetail, setRevisionDetail] = useState<RevisionDetail | null>(null)
  const [revisionDetailLoading, setRevisionDetailLoading] = useState(false)

  const { user } = useAuthStore()
  const isAdmin = user?.companies?.some((h) => h.role === 'admin') ?? false
  const canEdit = user?.companies?.some((h) => h.role === 'admin' || h.role === 'editor') ?? false
  const canAnalyze = user?.companies?.some((h) => h.role === 'admin' || h.role === 'editor') ?? false

  // ---- Version diff / compare state ----
  const [selectedVersions, setSelectedVersions] = useState<number[]>([])
  const [versionDiffResult, setVersionDiffResult] = useState<DiffResult | null>(null)
  const [versionDiffVisible, setVersionDiffVisible] = useState(false)
  const [versionDiffLoading, setVersionDiffLoading] = useState(false)
  const [uploadModalVisible, setUploadModalVisible] = useState(false)

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
      setVersions(data)
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

  // Load amendments
  const loadAmendments = useCallback(async () => {
    if (!documentId) return
    setAmendmentsLoading(true)
    try {
      const doc = currentDocument
      if (!doc) return
      if (doc.document_type === 'order') {
        const data = await getDocumentAmendedDocuments(documentId)
        setAmendedDocuments(data)
        setAmendments([])
      } else {
        const data = await getDocumentAmendments(documentId)
        setAmendments(data)
        setAmendedDocuments([])
      }
    } catch {
      // Silent fail
    } finally {
      setAmendmentsLoading(false)
    }
  }, [documentId, currentDocument])

  const loadHistory = useCallback(async () => {
    if (!documentId) return
    setHistoryLoading(true)
    try {
      const data = await getDocumentHistory(documentId)
      setStatusHistory(data)
    } catch {
      // Silent fail
    } finally {
      setHistoryLoading(false)
    }
  }, [documentId])

  // Load revisions
  const loadRevisions = useCallback(async () => {
    if (!documentId) return
    setRevisionsLoading(true)
    try {
      const data = await getDocumentRevisions(documentId)
      setRevisions(data)
    } catch {
      // Silent fail
    } finally {
      setRevisionsLoading(false)
    }
  }, [documentId])

  const handleViewRevisionDiff = useCallback(async (revisionId: number) => {
    if (!documentId) return
    setRevisionDetailLoading(true)
    setRevisionDetailModalVisible(true)
    try {
      const detail = await getDocumentRevisionDetail(documentId, revisionId)
      setRevisionDetail(detail)
    } catch {
      setRevisionDetail(null)
    } finally {
      setRevisionDetailLoading(false)
    }
  }, [documentId])

  // Load analysis history
  const loadAnalysisHistory = useCallback(async () => {
    if (!documentId) return
    setAnalysisHistoryLoading(true)
    try {
      const response = await getAnalysisHistory(documentId)
      const data = Array.isArray(response.data) ? response.data : []
      setAnalysisHistory(data)
    } catch {
      // Silently fail
    } finally {
      setAnalysisHistoryLoading(false)
    }
  }, [documentId])

  // Load detailed analysis status
  const loadAnalysisDetail = useCallback(async (analysisId: number) => {
    setSelectedAnalysisLoading(true)
    try {
      const response = await getAnalysisStatus(analysisId)
      setSelectedAnalysis(response.data)
    } catch {
      // Silently fail
    } finally {
      setSelectedAnalysisLoading(false)
    }
  }, [])

  // Poll for running analysis
  const startPolling = useCallback((analysisId: number) => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
    }
    pollTimerRef.current = setInterval(async () => {
      try {
        const response = await getAnalysisStatus(analysisId)
        const data: AnalysisStatusResponse = response.data
        setSelectedAnalysis(data)
        // If analysis is no longer running, stop polling and refresh doc
        if (data.status === 'complete' || data.status === 'error') {
          if (pollTimerRef.current) {
            clearInterval(pollTimerRef.current)
            pollTimerRef.current = undefined
          }
          fetchDocument(documentId)
          loadAnalysisHistory()
        }
      } catch {
        // Stop polling on error
        if (pollTimerRef.current) {
          clearInterval(pollTimerRef.current)
          pollTimerRef.current = undefined
        }
      }
    }, 3000)
  }, [documentId, fetchDocument, loadAnalysisHistory])

  // Load analysis history on mount if document has analysis data
  useEffect(() => {
    if (!currentDocument) return
    if (currentDocument.analysis_status && currentDocument.analysis_status !== 'none') {
      loadAnalysisHistory()
    }
  }, [currentDocument?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-start polling when analysis is running
  useEffect(() => {
    if (!currentDocument) return

    if (currentDocument.analysis_status === 'running') {
      // Find the running analysis in history
      const runningAnalysis = analysisHistory.find((a) => a.status === 'running')
      if (runningAnalysis) {
        loadAnalysisDetail(runningAnalysis.id)
        startPolling(runningAnalysis.id)
      }
    }

    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current)
        pollTimerRef.current = undefined
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentDocument?.analysis_status, analysisHistory.length])

  const handleLinkSearch = useCallback((value: string) => {
    setLinkSearchText(value)
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    if (!value || value.length < 2) {
      setLinkSearchResults([])
      return
    }
    setLinkSearchLoading(true)
    searchTimerRef.current = setTimeout(async () => {
      try {
        const result = await getDocuments({ search: value, page_size: 20 })
        const filtered = (result.items || []).filter(d => d.id !== documentId)
        setLinkSearchResults(filtered)
      } catch (err) {
        console.error('Search failed:', err)
        message.warning('Ошибка при поиске документов. Проверьте соединение.')
        setLinkSearchResults([])
      } finally {
        setLinkSearchLoading(false)
      }
    }, 300)
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
      case 'amendments':
        if (amendments.length === 0 && amendedDocuments.length === 0) loadAmendments()
        break
      case 'history':
        if (statusHistory.length === 0) loadHistory()
        break
      case 'analysis':
        if (analysisHistory.length === 0) loadAnalysisHistory()
        break
      case 'revisions':
        if (revisions.length === 0) loadRevisions()
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

  const handleDownloadByVersion = useCallback(async (versionNumber: number) => {
    try {
      await downloadVersion(documentId, versionNumber)
    } catch {
      message.error('Не удалось скачать версию')
    }
  }, [documentId])

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

  const handleReanalyze = async () => {
    if (!currentDocument) return
    setReanalyzing(true)
    try {
      const response = await reanalyzeDocument(currentDocument.id)
      const result = response.data
      message.success(result.message || 'Анализ запущен')
      // Refresh document and analysis history
      fetchDocument(documentId)
      await loadAnalysisHistory()
      // Select the new analysis for progress display
      if (result.analysis_id) {
        loadAnalysisDetail(result.analysis_id)
        startPolling(result.analysis_id)
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail?.message || err?.message || 'Ошибка запуска анализа'
      message.error(msg)
    } finally {
      setReanalyzing(false)
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

  // ---- Version handlers (Phase 7) ----
  const handleRestore = async (versionNumber: number) => {
    Modal.confirm({
      title: 'Восстановить версию',
      content: `Будет создана новая версия с содержимым v${versionNumber}. Продолжить?`,
      onOk: async () => {
        try {
          await restoreVersion(documentId, versionNumber)
          message.success(`Версия v${versionNumber} восстановлена`)
          loadVersions()
          fetchDocument(documentId)
        } catch (err: any) {
          message.error(err?.response?.data?.detail || 'Ошибка восстановления')
        }
      },
    })
  }

  const handleCompare = async () => {
    if (selectedVersions.length !== 2) return
    const [v1, v2] = [...selectedVersions].sort((a, b) => a - b)
    setVersionDiffLoading(true)
    try {
      const response = await compareVersions(documentId, v1, v2)
      setVersionDiffResult(response.diff)
      setVersionDiffVisible(true)
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Ошибка сравнения версий')
    } finally {
      setVersionDiffLoading(false)
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
    .filter((s) => {
      if (s === 'archived') return false  // handled by separate button
      if (s === doc.status) return true
      // Admin sees all statuses (no transition restrictions)
      if (isAdmin) return true
      // Non-admin: respect transition constraints
      if (s === 'cancelled') return doc.status === 'approved'
      if (doc.status === 'cancelled') return s === 'draft'
      return true
    })
    .map((s) => ({
      value: s,
      label: STATUS_LABELS[s],
      disabled: s === doc.status,
    }))

  // Columns for versions table
  const versionColumns: ColumnsType<VersionItem> = [
    {
      title: '',
      key: 'select',
      width: 40,
      render: (_, record) => (
        <Checkbox
          checked={selectedVersions.includes(record.version_number)}
          disabled={
            selectedVersions.length >= 2 &&
            !selectedVersions.includes(record.version_number)
          }
          onChange={(e) => {
            if (e.target.checked) {
              setSelectedVersions([...selectedVersions, record.version_number])
            } else {
              setSelectedVersions(selectedVersions.filter((v) => v !== record.version_number))
            }
          }}
        />
      ),
    },
    {
      title: 'Версия',
      dataIndex: 'version_number',
      key: 'version_number',
      width: 80,
      render: (v: number) => (
        <Space>
          <strong>v{v}</strong>
          {v === Math.max(...versions.map((x) => x.version_number)) && (
            <Tag color="blue">Текущая</Tag>
          )}
        </Space>
      ),
    },
    {
      title: 'Дата',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (d: string) => dayjs(d).format('DD.MM.YYYY HH:mm'),
    },
    {
      title: 'Размер',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 100,
      render: (s: number) => {
        if (!s) return '—'
        return `${(s / 1024).toFixed(1)} KB`
      },
    },
    {
      title: 'Комментарий',
      dataIndex: 'comment',
      key: 'comment',
      ellipsis: true,
      render: (c: string) => c || '—',
    },
    {
      title: 'Действия',
      key: 'actions',
      width: 160,
      render: (_, record) => (
        <Space>
          <Tooltip title="Скачать">
            <Button
              type="text"
              icon={<DownloadOutlined />}
              onClick={() => handleDownloadByVersion(record.version_number)}
            />
          </Tooltip>
          {canEdit && (
            <Tooltip title="Восстановить эту версию">
              <Button
                type="text"
                icon={<RestOutlined />}
                onClick={() => handleRestore(record.version_number)}
              />
            </Tooltip>
          )}
        </Space>
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
              {doc.document_type && (
                <Tag
                  color={
                    ({
                      regulation: 'blue',
                      order: 'orange',
                      provision: 'purple',
                      policy: 'green',
                      directive: 'cyan',
                    } as Record<string, string>)[doc.document_type] || 'default'
                  }
                >
                  {DOCUMENT_TYPE_LABELS[doc.document_type as DocumentType] || doc.document_type}
                </Tag>
              )}
              {doc.analysis_status && (
                <AnalysisStatusBadge status={doc.analysis_status} />
              )}
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

          {/* Revise button — for editor+ only */}
          {canEdit && doc.status !== 'archived' && (
            <Button
              icon={<EditOutlined />}
              onClick={() => setReviseModalVisible(true)}
            >
              Внести правки
            </Button>
          )}

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
                    <Descriptions.Item label="Тип документа">
                      {doc.document_type ? (
                        <Tag
                          color={
                            ({
                              regulation: 'blue',
                              order: 'orange',
                              provision: 'purple',
                              policy: 'green',
                              directive: 'cyan',
                            } as Record<string, string>)[doc.document_type] || 'default'
                          }
                        >
                          {DOCUMENT_TYPE_LABELS[doc.document_type as DocumentType] || doc.document_type}
                        </Tag>
                      ) : (
                        <Text type="secondary">—</Text>
                      )}
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
                <>
                  <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Space>
                      {doc.status !== 'archived' && (
                        <Button
                          type="primary"
                          icon={<UploadOutlined />}
                          onClick={() => setUploadModalVisible(true)}
                        >
                          Загрузить новую версию
                        </Button>
                      )}
                      {selectedVersions.length === 2 && (
                        <Button
                          icon={<DiffOutlined />}
                          loading={versionDiffLoading}
                          onClick={handleCompare}
                        >
                          Сравнить v{Math.min(...selectedVersions)} и v{Math.max(...selectedVersions)}
                        </Button>
                      )}
                    </Space>
                    {selectedVersions.length > 0 && (
                      <Button size="small" onClick={() => setSelectedVersions([])}>
                        Снять выбор ({selectedVersions.length})
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
                      rowKey="version_number"
                      columns={versionColumns}
                      pagination={false}
                      size="middle"
                    />
                  )}

                  <VersionUploadModal
                    visible={uploadModalVisible}
                    onClose={() => setUploadModalVisible(false)}
                    documentId={documentId}
                    onSuccess={() => {
                      loadVersions()
                      fetchDocument(documentId)
                    }}
                  />
                </>
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
                          onSearch={handleLinkSearch}
                          onChange={(value) => setNewLinkTargetId(value)}
                          style={{ width: '100%', marginTop: 4 }}
                          loading={linkSearchLoading}
                          options={linkSearchResults.map(doc => ({
                            value: doc.id,
                            label: `${doc.title} #${doc.id}`
                          }))}
                          optionRender={(option) => {
                            const doc = linkSearchResults.find(d => d.id === option.data.value)
                            if (!doc) return option.data.label ?? String(option.data.value)
                            return (
                              <Space>
                                <Tag color={STATUS_COLORS[doc.status]} style={{ marginRight: 4 }}>
                                  #{doc.id}
                                </Tag>
                                <span>{doc.title}</span>
                                <Tag color={STATUS_COLORS[doc.status]}>{STATUS_LABELS[doc.status]}</Tag>
                                <Text type="secondary" style={{ fontSize: 12 }}>
                                  {doc.file_type?.toUpperCase() ?? ''} v{doc.version_number ?? '?'}
                                </Text>
                              </Space>
                            )
                          }}
                        />
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
            {
              key: 'amendments',
              label: 'Изменения',
              children: (
                <div>
                  {amendmentsLoading ? (
                    <Spin style={{ display: 'block', margin: '40px auto' }} />
                  ) : doc.document_type === 'order' ? (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                        <Title level={5} style={{ margin: 0 }}>Вносит изменения в</Title>
                      </div>
                      {amendedDocuments.length === 0 ? (
                        <Empty description="Этот приказ не вносит изменения ни в один документ" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                      ) : (
                        <Table
                          dataSource={amendedDocuments}
                          rowKey="link_id"
                          pagination={false}
                          size="small"
                          columns={[
                            {
                              title: 'Название',
                              dataIndex: 'title',
                              key: 'title',
                              ellipsis: true,
                            },
                            {
                              title: 'Тип',
                              dataIndex: 'document_type',
                              key: 'document_type',
                              width: 120,
                              render: (type: string) => (
                                <Tag color={
                                  ({
                                    regulation: 'blue',
                                    order: 'orange',
                                    provision: 'purple',
                                    policy: 'green',
                                    directive: 'cyan',
                                  } as Record<string, string>)[type] || 'default'
                                }>
                                  {DOCUMENT_TYPE_LABELS[type as DocumentType] || type}
                                </Tag>
                              ),
                            },
                            {
                              title: 'Статус',
                              dataIndex: 'status',
                              key: 'status',
                              width: 140,
                              render: (status: string) => (
                                <Tag color={STATUS_COLORS[status as DocumentStatus]}>
                                  {STATUS_LABELS[status as DocumentStatus] || status}
                                </Tag>
                              ),
                            },
                            {
                              title: 'Дата связи',
                              dataIndex: 'created_at',
                              key: 'created_at',
                              width: 160,
                              render: (date: string) => dayjs(date).format('DD.MM.YYYY'),
                            },
                          ]}
                        />
                      )}
                    </>
                  ) : (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                        <Title level={5} style={{ margin: 0 }}>Изменяется приказами</Title>
                        {(canEdit && doc.document_type !== 'order') && (
                          <Button
                            type="primary"
                            size="small"
                            icon={<PlusOutlined />}
                            onClick={() => {
                              setNewLinkType('amends')
                              setLinkModalOpen(true)
                            }}
                          >
                            Связать с приказом
                          </Button>
                        )}
                      </div>
                      {amendments.length === 0 ? (
                        <Empty description="Нет приказов, изменяющих этот документ" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                      ) : (
                        <Table
                          dataSource={amendments}
                          rowKey="link_id"
                          pagination={false}
                          size="small"
                          columns={[
                            {
                              title: 'Приказ',
                              dataIndex: 'title',
                              key: 'title',
                              ellipsis: true,
                            },
                            {
                              title: 'Статус',
                              dataIndex: 'status',
                              key: 'status',
                              width: 140,
                              render: (status: string) => (
                                <Tag color={STATUS_COLORS[status as DocumentStatus]}>
                                  {STATUS_LABELS[status as DocumentStatus] || status}
                                </Tag>
                              ),
                            },
                            {
                              title: 'Дата связи',
                              dataIndex: 'created_at',
                              key: 'created_at',
                              width: 160,
                              render: (date: string) => dayjs(date).format('DD.MM.YYYY'),
                            },
                          ]}
                        />
                      )}
                    </>
                  )}
                </div>
              ),
            },
            {
              key: 'analysis',
              label: `Анализ${analysisHistory.length > 0 ? ` (${analysisHistory.length})` : ''}`,
              children: (
                <div>
                  {/* Current status badge */}
                  <div style={{ marginBottom: 16 }}>
                    <Space align="center" size="middle">
                      <Text strong>Статус анализа:</Text>
                      {doc.analysis_status ? (
                        <AnalysisStatusBadge status={doc.analysis_status} />
                      ) : (
                        <AnalysisStatusBadge status="none" />
                      )}
                      {doc.analysis_hash && (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          Hash: {doc.analysis_hash.slice(0, 12)}…
                        </Text>
                      )}
                    </Space>
                  </div>

                  {/* Reanalyze button */}
                  {doc.analysis_status !== 'running' && doc.status !== 'archived' && canAnalyze && (
                    <div style={{ marginBottom: 16 }}>
                      <Popconfirm
                        title="Перезапустить анализ?"
                        description="Будет запущен повторный анализ документа."
                        onConfirm={handleReanalyze}
                        okText="Запустить"
                        cancelText="Отмена"
                      >
                        <Button
                          type="primary"
                          icon={<ReloadOutlined />}
                          loading={reanalyzing}
                        >
                          Перезапустить анализ
                        </Button>
                      </Popconfirm>
                    </div>
                  )}

                  {/* Last pipeline progress */}
                  {selectedAnalysis && (
                    <Card
                      title="Прогресс pipeline"
                      size="small"
                      style={{ marginBottom: 16 }}
                    >
                      <AnalysisPipelineProgress
                        stepsStatus={selectedAnalysis.steps_status}
                        status={selectedAnalysis.status}
                        errorMessage={selectedAnalysis.error_message}
                        resultSummary={selectedAnalysis.result_summary}
                      />
                    </Card>
                  )}

                  {/* Analysis history table */}
                  <Title level={5} style={{ marginBottom: 16 }}>
                    История анализов
                  </Title>
                  {analysisHistoryLoading ? (
                    <Spin style={{ display: 'block', margin: '40px auto' }} />
                  ) : analysisHistory.length === 0 ? (
                    <Empty description="История анализов пуста" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    <Table
                      dataSource={analysisHistory}
                      rowKey="id"
                      pagination={false}
                      size="middle"
                      onRow={(record) => ({
                        onClick: () => {
                          loadAnalysisDetail(record.id)
                        },
                        style: { cursor: 'pointer' },
                      })}
                      columns={[
                        {
                          title: 'ID',
                          dataIndex: 'id',
                          key: 'id',
                          width: 70,
                        },
                        {
                          title: 'Дата запуска',
                          dataIndex: 'created_at',
                          key: 'created_at',
                          width: 160,
                          render: (date: string) => dayjs(date).format('DD.MM.YYYY HH:mm'),
                        },
                        {
                          title: 'Статус',
                          dataIndex: 'status',
                          key: 'status',
                          width: 120,
                          render: (status: string) => (
                            <Tag
                              color={
                                status === 'complete' ? 'success'
                                : status === 'error' ? 'error'
                                : 'processing'
                              }
                            >
                              {status === 'complete' ? 'Завершён'
                                : status === 'error' ? 'Ошибка'
                                : 'Выполняется…'}
                            </Tag>
                          ),
                        },
                        {
                          title: 'Ошибка',
                          dataIndex: 'error_message',
                          key: 'error_message',
                          ellipsis: true,
                          render: (val: string | null) =>
                            val || <Text type="secondary">—</Text>,
                        },
                        {
                          title: 'Результат',
                          key: 'result',
                          width: 200,
                          render: (_: any, record: AnalysisHistoryItem) => {
                            if (!record.result_summary) {
                              return <Text type="secondary">—</Text>
                            }
                            const parts: string[] = []
                            if (record.result_summary.sections_found !== undefined)
                              parts.push(`${record.result_summary.sections_found} разд.`)
                            if (record.result_summary.terms_found !== undefined)
                              parts.push(`${record.result_summary.terms_found} терм.`)
                            if (record.result_summary.abbreviations_found !== undefined)
                              parts.push(`${record.result_summary.abbreviations_found} сокр.`)
                            if (record.result_summary.references_found !== undefined)
                              parts.push(`${record.result_summary.references_found} ссылок`)
                            return parts.length > 0
                              ? <Text>{parts.join(', ')}</Text>
                              : <Text type="secondary">—</Text>
                          },
                        },
                      ]}
                    />
                  )}

                  {/* Detail progress for selected analysis */}
                  {selectedAnalysisLoading && (
                    <div style={{ marginTop: 16, textAlign: 'center' }}>
                      <Spin tip="Загрузка деталей анализа…" />
                    </div>
                  )}
                </div>
              ),
            },
            {
              key: 'history',
              label: `История статусов (${statusHistory.length})`,
              children: (
                <div>
                  {historyLoading ? (
                    <Spin style={{ display: 'block', margin: '40px auto' }} />
                  ) : statusHistory.length === 0 ? (
                    <Empty description="История статусов пуста" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    <Timeline
                      items={statusHistory.map((item) => ({
                        color: item.to_status === 'approved' ? 'green'
                               : item.to_status === 'cancelled' ? 'red'
                               : item.to_status === 'archived' ? 'gray'
                               : item.to_status === 'review' ? 'orange'
                               : 'blue',
                        children: (
                          <div>
                            <div>
                              <Tag>{item.from_status ? (STATUS_LABELS[item.from_status as DocumentStatus] || item.from_status) : '—'}</Tag>
                              <span style={{ margin: '0 8px' }}>→</span>
                              <Tag color={STATUS_COLORS[item.to_status as DocumentStatus]}>{STATUS_LABELS[item.to_status as DocumentStatus] || item.to_status}</Tag>
                            </div>
                            {item.reason && (
                              <div style={{ marginTop: 4, color: '#666' }}>
                                <em>{item.reason}</em>
                              </div>
                            )}
                            <div style={{ marginTop: 2, fontSize: 12, color: '#999' }}>
                              {item.changer_email || 'Система'} · {dayjs(item.created_at).format('DD.MM.YYYY HH:mm')}
                            </div>
                          </div>
                        ),
                      }))}
                    />
                  )}
                </div>
              ),
            },
            {
              key: 'revisions',
              label: `Ревизии (${revisions.length})`,
              children: (
                <div>
                  {revisionsLoading ? (
                    <Spin style={{ display: 'block', margin: '40px auto' }} />
                  ) : revisions.length === 0 ? (
                    <Empty
                      description="История ревизий пуста. Используйте кнопку «Внести правки», чтобы создать первую ревизию."
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                    />
                  ) : (
                    <Table
                      dataSource={revisions}
                      rowKey="id"
                      pagination={false}
                      size="middle"
                      columns={[
                        {
                          title: 'Дата',
                          dataIndex: 'created_at',
                          key: 'created_at',
                          width: 160,
                          render: (date: string) => dayjs(date).format('DD.MM.YYYY HH:mm'),
                        },
                        {
                          title: 'Комментарий',
                          dataIndex: 'comment',
                          key: 'comment',
                          ellipsis: true,
                          render: (text: string) => {
                            if (text.length > 100) {
                              return <span title={text}>{text.slice(0, 100)}…</span>
                            }
                            return text
                          },
                        },
                        {
                          title: 'Раздел',
                          dataIndex: 'target_section',
                          key: 'target_section',
                          width: 160,
                          render: (val: string | undefined) => val || <Text type="secondary">—</Text>,
                        },
                        {
                          title: 'Изменения',
                          key: 'stats',
                          width: 140,
                          render: (_: any, record: RevisionHistoryItem) => {
                            if (!record.stats) return <Text type="secondary">—</Text>
                            return (
                              <Text>
                                <Text style={{ color: '#52c41a' }}>+{record.stats.added}</Text>
                                /
                                <Text style={{ color: '#ff4d4f' }}>−{record.stats.removed}</Text>
                                {record.stats.changed > 0 && (
                                  <>
                                    {' '}/ <Text style={{ color: '#faad14' }}>~{record.stats.changed}</Text>
                                  </>
                                )}
                              </Text>
                            )
                          },
                        },
                        {
                          title: 'Кем',
                          dataIndex: 'created_by_email',
                          key: 'created_by_email',
                          width: 200,
                          render: (val: string | undefined) => val || <Text type="secondary">—</Text>,
                        },
                        {
                          title: 'Действия',
                          key: 'actions',
                          width: 160,
                          render: (_: any, record: RevisionHistoryItem) => (
                            <Button
                              type="link"
                              size="small"
                              onClick={() => handleViewRevisionDiff(record.id)}
                            >
                              Просмотреть diff
                            </Button>
                          ),
                        },
                      ]}
                    />
                  )}
                </div>
              ),
            },
          ]}
        />
      </Card>

      {/* Version Compare Modal */}
      <Modal
        title={
          versionDiffResult
            ? `Сравнение v${selectedVersions.sort((a, b) => a - b)[0]} и v${selectedVersions.sort((a, b) => a - b)[1]}`
            : 'Сравнение версий'
        }
        open={versionDiffVisible}
        onCancel={() => setVersionDiffVisible(false)}
        width="90%"
        style={{ top: 20 }}
        footer={[
          <Button key="close" onClick={() => setVersionDiffVisible(false)}>
            Закрыть
          </Button>,
        ]}
      >
        {versionDiffResult && (
          <DiffView
            oldText=""
            newText=""
            htmlDiff={versionDiffResult.html_diff}
            stats={versionDiffResult.stats}
            documentTitle={`Сравнение версий`}
            onClose={() => setVersionDiffVisible(false)}
          />
        )}
      </Modal>

      {/* Revise Modal */}
      <ReviseModal
        visible={reviseModalVisible}
        onClose={() => setReviseModalVisible(false)}
        documentId={documentId}
        onSuccess={(response) => {
          setReviseModalVisible(false)
          setDiffResult(response)
          setDiffVisible(true)
        }}
      />

      {/* Diff View Modal (from revise) */}
      <Modal
        title={`Изменения документа: ${diffResult?.document_title}`}
        open={diffVisible}
        onCancel={() => setDiffVisible(false)}
        width="90%"
        style={{ top: 20 }}
        footer={[
          <Button key="close" onClick={() => setDiffVisible(false)}>
            Закрыть
          </Button>,
        ]}
      >
        {diffResult && (
          <DiffView
            oldText={diffResult.old_text}
            newText={diffResult.new_text}
            htmlDiff={diffResult.diff.html_diff}
            stats={diffResult.diff.stats}
            documentTitle={diffResult.document_title}
            onClose={() => setDiffVisible(false)}
          />
        )}
      </Modal>

      {/* Revision Detail Diff Modal (from history) */}
      <Modal
        title={revisionDetail ? `Ревизия #${revisionDetail.id}` : 'Загрузка...'}
        open={revisionDetailModalVisible}
        onCancel={() => {
          setRevisionDetailModalVisible(false)
          setRevisionDetail(null)
        }}
        width="90%"
        style={{ top: 20 }}
        footer={[
          <Button key="close" onClick={() => {
            setRevisionDetailModalVisible(false)
            setRevisionDetail(null)
          }}>
            Закрыть
          </Button>,
        ]}
      >
        {revisionDetailLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin tip="Загрузка ревизии..." />
          </div>
        ) : revisionDetail ? (
          <DiffView
            oldText={revisionDetail.old_text}
            newText={revisionDetail.new_text}
            htmlDiff={revisionDetail.old_text !== revisionDetail.new_text
              ? buildHtmlDiffFromTexts(revisionDetail.old_text, revisionDetail.new_text)
              : '<table class="diff"><tr><td style="padding: 8px; color: #999;">Нет изменений</td></tr></table>'
            }
            stats={revisionDetail.stats || { added: 0, removed: 0, changed: 0 }}
            documentTitle={`Ревизия #${revisionDetail.id} — ${revisionDetail.comment}`}
            onClose={() => {
              setRevisionDetailModalVisible(false)
              setRevisionDetail(null)
            }}
          />
        ) : (
          <Empty description="Не удалось загрузить ревизию" />
        )}
      </Modal>

    </div>
  )
}

// Helper: build a simple HTML diff table from two texts
function buildHtmlDiffFromTexts(oldText: string, newText: string): string {
  const oldLines = oldText.split('\n')
  const newLines = newText.split('\n')
  let html = '<table class="diff" width="100%">'

  const maxLines = Math.max(oldLines.length, newLines.length)
  for (let i = 0; i < maxLines; i++) {
    const oldLine = oldLines[i] ?? ''
    const newLine = newLines[i] ?? ''
    let rowClass = ''
    let lineContent = ''

    if (oldLine !== newLine) {
      if (oldLine === '') {
        rowClass = 'diff_add'
        lineContent = `<td class="diff_header">${i + 1}</td><td></td><td class="diff_header">${i + 1}</td><td class="diff_add">${escapeHtml(newLine)}</td>`
      } else if (newLine === '') {
        rowClass = 'diff_sub'
        lineContent = `<td class="diff_header">${i + 1}</td><td class="diff_sub">${escapeHtml(oldLine)}</td><td class="diff_header">${i + 1}</td><td></td>`
      } else {
        rowClass = 'diff_chg'
        lineContent = `<td class="diff_header">${i + 1}</td><td class="diff_chg">${escapeHtml(oldLine)}</td><td class="diff_header">${i + 1}</td><td class="diff_chg">${escapeHtml(newLine)}</td>`
      }
    } else {
      lineContent = `<td class="diff_header">${i + 1}</td><td>${escapeHtml(oldLine)}</td><td class="diff_header">${i + 1}</td><td>${escapeHtml(newLine)}</td>`
    }

    html += `<tr class="${rowClass}">${lineContent}</tr>`
  }

  html += '</table>'
  return html
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}
