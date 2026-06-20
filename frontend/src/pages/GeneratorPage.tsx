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
} from 'antd'
import {
  RobotOutlined,
  InboxOutlined,
  DownloadOutlined,
  FileTextOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import type { UploadFile } from 'antd'
import { useGeneratorStore } from '../store/generatorStore'
import { getDocuments, getDownloadUrl } from '../api/documents'
import { USE_MSW } from '../api/client'
import type { DocumentListItem } from '../types'

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

export default function GeneratorPage() {
  const navigate = useNavigate()
  const { state, generate, reset } = useGeneratorStore()

  // Form state (kept locally to survive reset/store state transitions)
  const [context, setContext] = useState('')
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [influencingDocIds, setInfluencingDocIds] = useState<number[]>([])
  const [documents, setDocuments] = useState<DocumentListItem[]>([])
  const [docsLoading, setDocsLoading] = useState(false)

  // Load influencing documents list on mount
  useEffect(() => {
    setDocsLoading(true)
    getDocuments({ page: 1, page_size: 100 })
      .then((res) => setDocuments(res.items))
      .catch(() => {
        // Silently fail — select will just show no options
      })
      .finally(() => setDocsLoading(false))
  }, [])

  const isContextValid = context.trim().length >= 20

  const handleGenerate = useCallback(() => {
    if (!isContextValid) return

    const files: File[] = fileList
      .filter((f) => f.originFileObj)
      .map((f) => f.originFileObj as File)

    generate(context.trim(), files, influencingDocIds)
  }, [context, fileList, influencingDocIds, generate, isContextValid])

  const handleRetry = useCallback(() => {
    reset()
    // Local form state is preserved automatically
  }, [reset])

  const handleResetForm = useCallback(() => {
    reset()
    setContext('')
    setFileList([])
    setInfluencingDocIds([])
  }, [reset])

  const handleDownload = useCallback(() => {
    if (state.result?.current_version?.id) {
      const url = getDownloadUrl(state.result.current_version.id)
      window.open(url, '_blank')
    }
  }, [state.result])

  const handleOpenInRegistry = useCallback(() => {
    if (state.result?.id) {
      navigate(`/documents/${state.result.id}`)
    }
  }, [state.result, navigate])

  const isDemoMode = USE_MSW

  // ---- Render states ----

  // Progress / generating / formatting
  if (state.step === 'preparing' || state.step === 'generating' || state.step === 'formatting') {
    const currentStepIndex =
      state.step === 'preparing' ? 0 : state.step === 'generating' ? 1 : 2

    return (
      <div style={{ maxWidth: 720, margin: '0 auto' }}>
        <Title level={3} style={{ marginBottom: 32 }}>
          <RobotOutlined style={{ marginRight: 8 }} />
          Генерация документа
        </Title>

        <Card>
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Steps
              current={currentStepIndex}
              items={[
                { title: 'Подготовка', description: 'Анализ контекста' },
                { title: 'Генерация', description: 'Создание текста' },
                { title: 'Оформление', description: 'Форматирование DOCX' },
              ]}
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

  // Done
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

  // Error
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

  // ---- Form mode (default) ----
  return (
    <div style={{ maxWidth: 720, margin: '0 auto' }}>
      <Title level={3} style={{ marginBottom: 8 }}>
        <RobotOutlined style={{ marginRight: 8 }} />
        Генератор документов
      </Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        Опишите, какой документ нужно создать. Нейросеть GigaChat Pro подготовит
        проект регламента на основе вашего описания, приложенных черновиков и
        связанных документов.
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
          {/* Context description */}
          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>
              Контекстное описание <span style={{ color: '#ff4d4f' }}>*</span>
            </Text>
            <TextArea
              rows={8}
              placeholder="Опишите, что должен регулировать документ. Например: &quot;Регламент взаимодействия между отделами при согласовании договоров&quot;"
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

          {/* Draft files upload */}
          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>
              Загрузка черновиков
            </Text>
            <Dragger
              accept=".docx,.pdf"
              multiple
              fileList={fileList}
              beforeUpload={(file) => {
                setFileList((prev) => [
                  ...prev,
                  {
                    uid: `-${Date.now()}-${prev.length}`,
                    name: file.name,
                    status: 'done',
                    size: file.size,
                    originFileObj: file,
                  },
                ])
                return false
              }}
              onRemove={(file) => {
                setFileList((prev) => prev.filter((f) => f.uid !== file.uid))
              }}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">
                Перетащите файлы сюда или нажмите для выбора
              </p>
              <p className="ant-upload-hint">
                Поддерживаются форматы .docx и .pdf
              </p>
            </Dragger>
          </div>

          {/* Influencing documents */}
          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>
              Влияющие документы
            </Text>
            <Select
              mode="multiple"
              showSearch
              placeholder="Выберите документы из реестра"
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
              notFoundContent={docsLoading ? <Spin size="small" /> : 'Нет документов'}
            />
          </div>

          {/* Generate button */}
          <Button
            type="primary"
            size="large"
            icon={<RobotOutlined />}
            disabled={!isContextValid}
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
