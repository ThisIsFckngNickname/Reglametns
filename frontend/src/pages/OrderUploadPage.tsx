import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card,
  Form,
  Input,
  DatePicker,
  Button,
  Upload,
  Typography,
  Progress,
  Alert,
  Breadcrumb,
  Space,
  message,
} from 'antd'
import {
  UploadOutlined,
  ArrowLeftOutlined,
  InboxOutlined,
} from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload'
import dayjs from 'dayjs'
import { uploadOrder } from '../api/orders'

const { Title, Text } = Typography
const { Dragger } = Upload
const { TextArea } = Input

interface UploadFormValues {
  title: string
  order_number?: string
  order_date?: dayjs.Dayjs
  description?: string
}

export default function OrderUploadPage() {
  const navigate = useNavigate()
  const [form] = Form.useForm<UploadFormValues>()
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (fileList.length === 0) {
        message.error('Выберите файл приказа')
        return
      }

      const file = fileList[0].originFileObj
      if (!file) {
        message.error('Файл не найден')
        return
      }

      setUploading(true)
      setError(null)
      setUploadProgress(0)

      const orderDate = values.order_date
        ? values.order_date.format('YYYY-MM-DD')
        : undefined

      const result = await uploadOrder(
        file,
        values.title,
        values.order_number,
        orderDate,
        values.description,
        (percent) => setUploadProgress(percent)
      )

      message.success('Приказ успешно загружен')
      navigate(`/orders/${result.id}`)
    } catch (err: any) {
      if (err?.errorFields) {
        // Validation error from form, do nothing extra
        return
      }
      const msg =
        err?.response?.data?.detail?.message ||
        err?.message ||
        'Ошибка загрузки приказа'
      setError(msg)
    } finally {
      setUploading(false)
    }
  }

  const handleFileRemove = () => {
    setFileList([])
  }

  return (
    <div style={{ padding: 24, maxWidth: 700, margin: '0 auto' }}>
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
            title: 'Загрузка приказа',
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

      <Title level={3}>Загрузка приказа</Title>

      <Card>
        {error && (
          <Alert
            message="Ошибка загрузки"
            description={error}
            type="error"
            showIcon
            closable
            onClose={() => setError(null)}
            style={{ marginBottom: 16 }}
          />
        )}

        <Form
          form={form}
          layout="vertical"
          initialValues={{ title: '' }}
          requiredMark="optional"
        >
          <Form.Item
            name="title"
            label="Название приказа"
            rules={[{ required: true, message: 'Введите название приказа' }]}
          >
            <Input placeholder="Например: Об утверждении регламента..." />
          </Form.Item>

          <Space style={{ width: '100%' }} size="large">
            <Form.Item
              name="order_number"
              label="Номер приказа"
              style={{ flex: 1 }}
            >
              <Input placeholder="Например: 45-ОД" />
            </Form.Item>

            <Form.Item
              name="order_date"
              label="Дата приказа"
              style={{ flex: 1 }}
            >
              <DatePicker
                style={{ width: '100%' }}
                placeholder="Выберите дату"
                format="DD.MM.YYYY"
              />
            </Form.Item>
          </Space>

          <Form.Item
            name="description"
            label="Описание"
          >
            <TextArea
              rows={3}
              placeholder="Краткое описание приказа (необязательно)"
            />
          </Form.Item>

          <Form.Item
            label="Файл приказа"
            required
            help="Поддерживаются форматы DOCX и PDF"
          >
            <Dragger
              multiple={false}
              accept=".docx,.pdf"
              fileList={fileList}
              onRemove={handleFileRemove}
              beforeUpload={(file) => {
                const isValid =
                  file.type === 'application/pdf' ||
                  file.name.endsWith('.docx') ||
                  file.name.endsWith('.pdf')
                if (!isValid) {
                  message.error('Допустимы только файлы DOCX и PDF')
                  return Upload.LIST_IGNORE
                }
                setFileList([file as UploadFile])
                return false // Prevent automatic upload
              }}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">
                Нажмите или перетащите файл сюда
              </p>
              <p className="ant-upload-hint">
                DOCX или PDF, до 50 MB
              </p>
            </Dragger>
          </Form.Item>

          {uploading && (
            <div style={{ marginBottom: 16 }}>
              <Text type="secondary">Загрузка...</Text>
              <Progress percent={uploadProgress} status="active" />
            </div>
          )}

          <Button
            type="primary"
            icon={<UploadOutlined />}
            onClick={handleSubmit}
            loading={uploading}
            size="large"
            block
          >
            {uploading ? 'Загрузка...' : 'Загрузить приказ'}
          </Button>
        </Form>
      </Card>
    </div>
  )
}
