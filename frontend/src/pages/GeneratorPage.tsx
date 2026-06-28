import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card,
  Form,
  Input,
  Upload,
  Select,
  Button,
  Alert,
  Progress,
  Steps,
  Spin,
  Typography,
  Space,
  Result,
  Tag,
  message,
  Checkbox,
  Radio,
} from 'antd'
import {
  RobotOutlined,
  InboxOutlined,
  DownloadOutlined,
  FileTextOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  GlobalOutlined,
} from '@ant-design/icons'
import type { UploadFile, RcFile } from 'antd/es/upload/interface'
import { useGeneratorStore } from '../store/generatorStore'
import { useAuthStore } from '../store/authStore'
import { getDocuments, getDocument, downloadDocumentVersion, uploadDocument } from '../api/documents'
import { USE_MSW } from '../api/client'
import type { DocumentListItem } from '../types'
import { DOCUMENT_TYPE_OPTIONS } from '../types/companyTerms'
import type { DocumentType } from '../types/companyTerms'

const { TextArea } = Input
const { Dragger } = Upload
const { Title, Text } = Typography

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Б'
  const k = 1024
  const sizes = ['Б', 'КБ', 'МБ', 'ГБ']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

/**
 * Upload a draft file and return the document version ID.
 * Uses the existing upload endpoint, then fetches the document
 * to extract current_version.id.
 */
async function uploadDraftFile(file: File): Promise<number> {
  const uploadResult = await uploadDocument(file)
  const docId = uploadResult.id
  // Fetch the full document to get current version ID
  const docDetail = await getDocument(docId)
  const versionId = docDetail.current_version?.id
  if (!versionId) {
    throw new Error('Не удалось получить ID версии загруженного черновика')
  }
  return versionId
}

export default function GeneratorPage() {
  const navigate = useNavigate()
  const { state, generateV2, reset } = useGeneratorStore()
  const { user } = useAuthStore()
  const companyId = user?.active_company?.id

  // Form state
  const [context, setContext] = useState('')
  const [documentType, setDocumentType] = useState<DocumentType>('regulation')
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [draftFileId, setDraftFileId] = useState<number | null>(null)
  const [influencingDocIds, setInfluencingDocIds] = useState<number[]>([])
  const [searchEnabled, setSearchEnabled] = useState(true)
  const [documents, setDocuments] = useState<DocumentListItem[]>([])
  const [docsLoading, setDocsLoading] = useState(false)
  const [draftUploading, setDraftUploading] = useState(false)

  // Load influencing documents list on mount
  useEffect(() => {
    setDocsLoading(true)
    getDocuments({ page: 1, page_size: 100, status: 'approved' })
      .then((res) => setDocuments(res.items))
      .catch(() => {
        // Silently fail
      })
      .finally(() => setDocsLoading(false))
  }, [])

  const isContextValid = context.trim().length >= 20

  // Draft file upload handler
  const handleDraftUpload = useCallback(async (file: RcFile): Promise<false> => {
    setDraftUploading(true)
    try {
      const versionId = await uploadDraftFile(file)
      setDraftFileId(versionId)
      setFileList([
        {
          uid: `-${Date.now()}`,
          name: file.name,
          status: 'done',
          size: file.size,
          originFileObj: file,
        },
      ])
      message.success(`Черновик "${file.name}" загружен`)
    } catch (err: any) {
      message.error(err?.response?.data?.detail?.message || 'Ошибка загрузки черновика')
    } finally {
      setDraftUploading(false)
    }
    return false
  }, [])

  const handleDraftRemove = useCallback(() => {
    setFileList([])
    setDraftFileId(null)
  }, [])

  const handleGenerate = useCallback(() => {
    if (!isContextValid || !companyId) return

    generateV2({
      topic: context.trim(),
      document_type: documentType,
      company_id: companyId,
      draft_file_id: draftFileId,
      influence_document_ids: influencingDocIds.length > 0 ? influencingDocIds : undefined,
      search_enabled: searchEnabled,
    })
  }, [context, documentType, companyId, draftFileId, influencingDocIds, searchEnabled, generateV2, isContextValid])

  const handleRetry = useCallback(() => {
    reset()
  }, [reset])

  const handleResetForm = useCallback(() => {
    reset()
    setContext('')
    setDocumentType('regulation')
    setFileList([])
    setDraftFileId(null)
    setInfluencingDocIds([])
    setSearchEnabled(true)
  }, [reset])

  const handleDownload = useCallback(async () => {
    const result = state.result
    if (result?.current_version?.id) {
      try {
        const ext = result.current_version.file_type === 'pdf' ? 'pdf' : 'docx'
        const filename = `${result.title.replace(/[<>:"/\\|?*]/g, '_')}_v${result.current_version.version_number}.${ext}`
        await downloadDocumentVersion(result.current_version.id, filename)
      } catch {
        message.error('Не удалось скачать документ')
      }
    }
  }, [state.result])

  const handleOpenInRegistry = useCallback(() => {
    if (state.result?.id) {
      navigate(`/documents/${state.result.id}`)
    }
  }, [state.result, navigate])

  const isDemoMode = USE_MSW

  // Map V2 step to step index for display
  const getStepIndex = (step: string): number => {
    const stepOrder = ['preparing', 'searching', 'analyzing', 'generating', 'formatting']
    const idx = stepOrder.indexOf(step)
    return idx >= 0 ? idx : 0
  }

  // ─── Render: Progress/Generation ───────────────────────────────────
  if (
    state.step === 'preparing' ||
    state.step === 'searching' ||
    state.step === 'analyzing' ||
    state.step === 'generating' ||
    state.step === 'formatting'
  ) {
    const stepItems = [
      { title: 'Подготовка', description: 'Контекст и профиль' },
      { title: 'Поиск информации', description: 'Интернет-поиск' },
      { title: 'Анализ документов', description: 'Внутренние документы' },
      { title: 'Генерация', description: 'Создание текста' },
      { title: 'Оформление', description: 'Форматирование DOCX' },
    ]

    return (
      <div style={{ maxWidth: 720, margin: '0 auto' }}>
        <Title level={3} style={{ marginBottom: 32 }}>
          <RobotOutlined style={{ marginRight: 8 }} />
          Генерация документа
        </Title>

        <Card>
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Steps
              current={getStepIndex(state.step)}
              items={stepItems}
            />

            <div style={{ textAlign: 'center', padding: '24px 0' }}>
              <Spin size="large" />
            </div>

            <Progress percent={state.progress} strokeColor="#1677ff" />

            <Text type="secondary" style={{ textAlign: 'center', display: 'block' }}>
              {state.message}
            </Text>
          </Space>
        </Card>
      </div>
    )
  }

  // ─── Render: Done ───────────────────────────────────────────────────
  if (state.step === 'done' && state.result) {
    const { result } = state

    return (
      <div style={{ maxWidth: 720, margin: '0 auto' }}>
        <Title level={3} style={{ marginBottom: 32 }}>
          <RobotOutlined style={{ marginRight: 8 }} />
          Генерация завершена
        </Title>

        {isDemoMode && result.generated_with_mock && (
          <Alert
            type="warning"
            message="Демо-режим: GigaChat не подключён"
            description="Документ сгенерирован в демо-режиме. Для полноценной работы подключите GigaChat Pro."
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        <Alert
          type="success"
          message="Документ успешно сгенерирован!"
          showIcon
          style={{ marginBottom: 16 }}
        />

        <Card>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <div>
              <Text strong style={{ fontSize: 16 }}>{result.title}</Text>
            </div>

            <Space>
              <Tag color="blue">DOCX</Tag>
              <Tag>{formatFileSize(result.file_size)}</Tag>
              <Tag color="default">Черновик</Tag>
            </Space>

            {result.current_version && (
              <div>
                <Text type="secondary">
                  Версия {result.current_version.version_number} —{' '}
                  {new Date(result.created_at).toLocaleString('ru-RU')}
                </Text>
              </div>
            )}

            <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: 16 }}>
              <Space wrap>
                <Button
                  type="primary"
                  icon={<DownloadOutlined />}
                  size="large"
                  onClick={handleDownload}
                >
                  Скачать документ
                </Button>
                <Button
                  icon={<FileTextOutlined />}
                  size="large"
                  onClick={handleOpenInRegistry}
                >
                  Открыть в реестре
                </Button>
                <Button
                  icon={<ReloadOutlined />}
                  size="large"
                  onClick={handleResetForm}
                >
                  Сгенерировать ещё
                </Button>
              </Space>
            </div>
          </Space>
        </Card>
      </div>
    )
  }

  // ─── Render: Error ──────────────────────────────────────────────────
  if (state.step === 'error') {
    return (
      <div style={{ maxWidth: 720, margin: '0 auto' }}>
        <Title level={3} style={{ marginBottom: 32 }}>
          <RobotOutlined style={{ marginRight: 8 }} />
          Генерация документа
        </Title>

        <Result
          status="error"
          title="Ошибка генерации"
          subTitle={state.error || 'Произошла неизвестная ошибка'}
          extra={[
            <Button
              key="retry"
              type="primary"
              icon={<ReloadOutlined />}
              size="large"
              onClick={handleRetry}
            >
              Попробовать снова
            </Button>,
          ]}
        />
      </div>
    )
  }

  // ─── Render: Form ───────────────────────────────────────────────────
  return (
    <div style={{ maxWidth: 720, margin: '0 auto' }}>
      <Title level={3} style={{ marginBottom: 8 }}>
        <RobotOutlined style={{ marginRight: 8 }} />
        Генератор документов
      </Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        Опишите, какой документ нужно создать. Нейросеть подготовит
        проект регламента на основе вашего описания, приложенного черновика,
        документов холдинга и актуального законодательства.
      </Text>

      {isDemoMode && (
        <Alert
          type="warning"
          message="Демо-режим"
          description="GigaChat не подключён. Документ будет сгенерирован в демо-режиме с использованием мок-данных."
          showIcon
          icon={<ThunderboltOutlined />}
          style={{ marginBottom: 16 }}
        />
      )}

      <Card>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {/* Document type */}
          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>
              Тип документа
            </Text>
            <Radio.Group
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value)}
              optionType="button"
              buttonStyle="solid"
            >
              {DOCUMENT_TYPE_OPTIONS.map((opt) => (
                <Radio.Button key={opt.value} value={opt.value}>
                  {opt.label}
                </Radio.Button>
              ))}
            </Radio.Group>
          </div>

          {/* Topic description */}
          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>
              Тема документа <span style={{ color: '#ff4d4f' }}>*</span>
            </Text>
            <TextArea
              rows={6}
              placeholder="Опишите тему документа. Например: &quot;Регламент по ведению учёта горюче-смазочных материалов на предприятии&quot;"
              value={context}
              onChange={(e) => setContext(e.target.value)}
              showCount
              maxLength={10000}
              status={context.length > 0 && context.length < 20 ? 'error' : undefined}
            />
            {context.length > 0 && context.length < 20 && (
              <Text type="danger" style={{ fontSize: 12, marginTop: 4, display: 'block' }}>
                Минимум 20 символов
              </Text>
            )}
          </div>

          {/* Draft file upload */}
          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>
              Черновик документа (опционально)
            </Text>
            <Dragger
              accept=".docx,.txt"
              multiple={false}
              fileList={fileList}
              beforeUpload={handleDraftUpload}
              onRemove={handleDraftRemove}
              disabled={draftUploading}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">
                Перетащите файл сюда или нажмите для выбора
              </p>
              <p className="ant-upload-hint">
                Поддерживаются форматы .docx, .txt. Черновик будет загружен на сервер.
              </p>
            </Dragger>
            {draftUploading && (
              <Space style={{ marginTop: 8 }}>
                <Spin size="small" />
                <Text type="secondary">Загрузка черновика...</Text>
              </Space>
            )}
          </div>

          {/* Influencing documents */}
          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>
              Влияющие документы (опционально)
            </Text>
            <Select
              mode="multiple"
              showSearch
              placeholder="Выберите утверждённые документы из реестра"
              loading={docsLoading}
              value={influencingDocIds}
              onChange={setInfluencingDocIds}
              style={{ width: '100%' }}
              filterOption={(input, option) =>
                (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
              }
              options={documents.map((doc) => ({
                value: doc.id,
                label: `ID: ${doc.id} — ${doc.title}`,
              }))}
              notFoundContent={docsLoading ? <Spin size="small" /> : 'Нет утверждённых документов'}
            />
          </div>

          {/* Search enabled */}
          <div>
            <Checkbox
              checked={searchEnabled}
              onChange={(e) => setSearchEnabled(e.target.checked)}
            >
              <Space>
                <GlobalOutlined />
                <span>Искать информацию в интернете</span>
              </Space>
            </Checkbox>
            <br />
            <Text type="secondary" style={{ fontSize: 12 }}>
              При включении нейросеть будет искать актуальные нормативные документы и
              законодательство по теме.
            </Text>
          </div>

          {/* Generate button */}
          <Button
            type="primary"
            size="large"
            icon={<RobotOutlined />}
            disabled={!isContextValid || !companyId}
            onClick={handleGenerate}
            block
            style={{ height: 48, fontSize: 16 }}
          >
            Сгенерировать документ
          </Button>
        </Space>
      </Card>
    </div>
  )
}
