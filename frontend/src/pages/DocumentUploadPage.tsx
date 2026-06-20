import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Upload,
  Form,
  Input,
  Button,
  Card,
  Typography,
  Progress,
  Alert,
  message,
  Space,
} from 'antd'
import { InboxOutlined, ArrowLeftOutlined } from '@ant-design/icons'
import type { UploadFile, RcFile } from 'antd/es/upload/interface'
import { uploadDocument } from '../api/documents'
import { getApiErrorMessage } from '../api/client'

const { Title, Text } = Typography
const { Dragger } = Upload

const MAX_FILE_SIZE = 20 * 1024 * 1024 // 20 MB
const ALLOWED_TYPES = [
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/pdf',
]

export default function DocumentUploadPage() {
  const navigate = useNavigate()
  const [form] = Form.useForm()

  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [uploadedDocId, setUploadedDocId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const beforeUpload = (file: RcFile): boolean => {
    const isValidType = ALLOWED_TYPES.includes(file.type)
    if (!isValidType) {
      message.error('Разрешены только файлы DOCX и PDF')
      return false
    }

    const isValidSize = file.size <= MAX_FILE_SIZE
    if (!isValidSize) {
      message.error('Файл должен быть не больше 20 MB')
      return false
    }

    return false // Prevent auto-upload
  }

  const handleFileChange = (info: { fileList: UploadFile[] }) => {
    setFileList(info.fileList.slice(-1)) // Keep only the latest file
    setError(null)
  }

  const handleUpload = async () => {
    const file = fileList[0]?.originFileObj
    if (!file) {
      message.warning('Выберите файл для загрузки')
      return
    }

    setUploading(true)
    setProgress(0)
    setError(null)

    try {
      const values = await form.validateFields()
      const result = await uploadDocument(
        file,
        values.title || undefined,
        values.description || undefined,
        (percent) => setProgress(percent)
      )
      setUploadedDocId(result.id)
      message.success('Документ успешно загружен и обработан')
    } catch (err: any) {
      if (err?.errorFields) {
        // Form validation error
        return
      }
      const msg = getApiErrorMessage(err)
      setError(msg)
      message.error(msg)
    } finally {
      setUploading(false)
    }
  }

  const handleReset = () => {
    setFileList([])
    setProgress(0)
    setUploadedDocId(null)
    setError(null)
    form.resetFields()
  }

  if (uploadedDocId) {
    return (
      <div style={{ padding: 24, maxWidth: 600, margin: '0 auto' }}>
        <Card>
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Title level={3}>Документ успешно загружен</Title>
            <Text type="secondary">
              Документ загружен, распарсен и готов к просмотру
            </Text>
            <div style={{ marginTop: 24 }}>
              <Space>
                <Button
                  type="primary"
                  size="large"
                  onClick={() => navigate(`/documents/${uploadedDocId}`)}
                >
                  Перейти к документу
                </Button>
                <Button size="large" onClick={handleReset}>
                  Загрузить ещё
                </Button>
              </Space>
            </div>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div style={{ padding: 24, maxWidth: 700, margin: '0 auto' }}>
      <Button
        type="link"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/documents')}
        style={{ padding: 0, marginBottom: 16 }}
      >
        Назад к реестру
      </Button>

      <Title level={3}>Загрузка документа</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        Загрузите документ в формате DOCX или PDF (максимум 20 MB).
        После загрузки документ будет автоматически распарсен: извлечена
        структура разделов, таблицы, термины и сокращения.
      </Text>

      <Card>
        <Form form={form} layout="vertical">
          <Form.Item
            name="file"
            label="Файл документа"
            rules={[{ required: true, message: 'Выберите файл' }]}
          >
            <Dragger
              fileList={fileList}
              beforeUpload={beforeUpload}
              onChange={handleFileChange}
              onRemove={() => setFileList([])}
              accept=".docx,.pdf"
              multiple={false}
              maxCount={1}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">
                Нажмите или перетащите файл в эту область
              </p>
              <p className="ant-upload-hint">
                Поддерживаются форматы DOCX и PDF до 20 MB
              </p>
            </Dragger>
          </Form.Item>

          <Form.Item
            name="title"
            label="Название документа (опционально)"
          >
            <Input
              placeholder="Если не указано, будет использовано имя файла"
              maxLength={255}
            />
          </Form.Item>

          <Form.Item
            name="description"
            label="Описание (опционально)"
          >
            <Input.TextArea
              rows={3}
              placeholder="Краткое описание документа"
              maxLength={1000}
            />
          </Form.Item>

          {error && (
            <Alert
              message={error}
              type="error"
              showIcon
              closable
              onClose={() => setError(null)}
              style={{ marginBottom: 16 }}
            />
          )}

          {uploading && (
            <div style={{ marginBottom: 16 }}>
              <Text type="secondary">Загрузка...</Text>
              <Progress percent={progress} status="active" />
            </div>
          )}

          <Form.Item>
            <Space>
              <Button
                type="primary"
                onClick={handleUpload}
                loading={uploading}
                disabled={fileList.length === 0}
                icon={<InboxOutlined />}
              >
                {uploading ? 'Загрузка...' : 'Загрузить'}
              </Button>
              <Button onClick={handleReset} disabled={uploading}>
                Очистить
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
