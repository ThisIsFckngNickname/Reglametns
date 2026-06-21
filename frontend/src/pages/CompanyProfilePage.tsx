import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card,
  Typography,
  Tabs,
  Form,
  Input,
  Select,
  Button,
  Spin,
  Alert,
  Space,
  Tag,
  Checkbox,
  Divider,
  message,
  Breadcrumb,
  List,
} from 'antd'
import {
  SaveOutlined,
  ArrowLeftOutlined,
  LockOutlined,
  GlobalOutlined,
  BankOutlined,
} from '@ant-design/icons'
import { getCompanyProfile, updateCompanyProfile } from '../api/companies'
import { getApiErrorMessage } from '../api/client'
import type { CompanyProfile, AvailableSource } from '../types'

const { Title, Text, Paragraph } = Typography

const LEGAL_FORM_OPTIONS = [
  { value: 'ООО', label: 'ООО' },
  { value: 'АО', label: 'АО' },
  { value: 'ПАО', label: 'ПАО' },
  { value: 'иное', label: 'Иное' },
]

type PageState = 'loading' | 'ready' | 'error'

export default function CompanyProfilePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [form] = Form.useForm()

  const [profile, setProfile] = useState<CompanyProfile | null>(null)
  const [availableSources, setAvailableSources] = useState<AvailableSource[]>([])
  const [selectedSources, setSelectedSources] = useState<string[]>([])
  const [pageState, setPageState] = useState<PageState>('loading')
  const [errorMessage, setErrorMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const [activeTab, setActiveTab] = useState('settings')

  const companyId = id ? parseInt(id) : 0

  const loadProfile = useCallback(async () => {
    if (!companyId) return
    setPageState('loading')
    try {
      const data = await getCompanyProfile(companyId)
      setProfile(data)
      setAvailableSources(data.available_sources || [])
      setSelectedSources(data.active_sources)

      form.setFieldsValue({
        name: data.name,
        inn: data.inn,
        legal_form: data.legal_form,
      })
      setPageState('ready')
    } catch (err) {
      setErrorMessage(getApiErrorMessage(err))
      setPageState('error')
    }
  }, [companyId, form])

  useEffect(() => {
    loadProfile()
  }, [loadProfile])

  // ---- Save settings tab ----
  const handleSaveSettings = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)
      const updated = await updateCompanyProfile(companyId, {
        name: values.name,
        inn: values.inn || null,
        legal_form: values.legal_form,
      })
      setProfile(updated)
      message.success('Настройки сохранены')
    } catch (err: any) {
      if (err?.errorFields) return
      message.error(getApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  // ---- Save sources tab ----
  const handleSaveSources = async () => {
    setSaving(true)
    try {
      const updated = await updateCompanyProfile(companyId, {
        active_sources: selectedSources,
      })
      setProfile(updated)
      setAvailableSources(updated.available_sources || [])
      message.success('Источники сохранены')
    } catch (err) {
      message.error(getApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  // ---- Toggle source selection ----
  const handleToggleSource = (sourceId: string, checked: boolean) => {
    if (checked) {
      setSelectedSources((prev) => [...prev, sourceId])
    } else {
      setSelectedSources((prev) => prev.filter((s) => s !== sourceId))
    }
  }

  // ---- Render source item ----
  const renderSourceItem = (source: AvailableSource) => {
    const isChecked = selectedSources.includes(source.id)
    const isDisabled = !isChecked && source.is_paid

    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '12px 16px',
          border: '1px solid #f0f0f0',
          borderRadius: 8,
          marginBottom: 8,
          background: isChecked ? '#f6ffed' : '#fff',
          opacity: isDisabled ? 0.6 : 1,
          transition: 'all 0.2s',
        }}
      >
        <Checkbox
          checked={isChecked}
          onChange={(e) => handleToggleSource(source.id, e.target.checked)}
          disabled={isDisabled}
          style={{ marginRight: 12 }}
        />
        <div style={{ flex: 1 }}>
          <Space align="center">
            <GlobalOutlined style={{ color: '#1890ff', fontSize: 16 }} />
            <Text strong>{source.display_name}</Text>
            {source.is_paid ? (
              <Tag color="gold" icon={<LockOutlined />}>
                платно
              </Tag>
            ) : (
              <Tag color="green">бесплатно</Tag>
            )}
            {source.is_builtin && (
              <Tag color="blue">встроенный</Tag>
            )}
          </Space>
          <div style={{ marginTop: 4 }}>
            <Text type="secondary" style={{ fontSize: 13 }}>
              {source.description}
            </Text>
          </div>
        </div>
        {source.is_paid && !isChecked && (
          <LockOutlined style={{ color: '#faad14', fontSize: 18, marginLeft: 8 }} />
        )}
      </div>
    )
  }

  // ---- Loading ----
  if (pageState === 'loading') {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '80px 0' }}>
        <Spin size="large" tip="Загрузка профиля компании..." />
      </div>
    )
  }

  // ---- Error ----
  if (pageState === 'error') {
    return (
      <div style={{ padding: 24 }}>
        <Breadcrumb
          items={[
            { title: <span onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>Главная</span> },
            { title: 'Профиль компании' },
          ]}
          style={{ marginBottom: 16 }}
        />
        <Alert
          message="Ошибка загрузки"
          description={errorMessage}
          type="error"
          showIcon
          action={
            <Button onClick={loadProfile} size="small">
              Повторить
            </Button>
          }
        />
      </div>
    )
  }

  const tabItems = [
    {
      key: 'settings',
      label: (
        <span>
          <BankOutlined style={{ marginRight: 4 }} />
          Основные настройки
        </span>
      ),
      children: (
        <Card>
          <Form
            form={form}
            layout="vertical"
            style={{ maxWidth: 520 }}
          >
            <Form.Item
              name="name"
              label="Наименование компании"
              rules={[
                { required: true, message: 'Введите наименование компании' },
                { max: 255, message: 'Максимум 255 символов' },
              ]}
            >
              <Input placeholder='Например: ООО "Ромашка"' />
            </Form.Item>

            <Form.Item
              name="inn"
              label="ИНН"
              rules={[
                {
                  pattern: /^\d{10}$|^\d{12}$/,
                  message: 'ИНН должен содержать 10 или 12 цифр',
                },
              ]}
            >
              <Input placeholder="10 или 12 цифр (опционально)" maxLength={12} />
            </Form.Item>

            <Form.Item
              name="legal_form"
              label="Юридическая форма"
              rules={[{ required: true, message: 'Выберите юридическую форму' }]}
            >
              <Select placeholder="Выберите форму" options={LEGAL_FORM_OPTIONS} />
            </Form.Item>

            <Form.Item>
              <Button
                type="primary"
                icon={<SaveOutlined />}
                onClick={handleSaveSettings}
                loading={saving}
                size="large"
              >
                Сохранить настройки
              </Button>
            </Form.Item>
          </Form>
        </Card>
      ),
    },
    {
      key: 'sources',
      label: (
        <span>
          <GlobalOutlined style={{ marginRight: 4 }} />
          Источники законодательства
        </span>
      ),
      children: (
        <Card>
          <Space direction="vertical" style={{ width: '100%' }}>
            <div>
              <Title level={5} style={{ marginBottom: 4 }}>Источники законодательства</Title>
              <Paragraph type="secondary" style={{ marginBottom: 16 }}>
                Выберите источники, по которым будет выполняться поиск законодательства
              </Paragraph>
            </div>

            {/* Built-in sources */}
            {availableSources.filter((s) => s.is_builtin).length > 0 && (
              <>
                <Text strong style={{ marginBottom: 8, display: 'block' }}>
                  Встроенные источники
                </Text>
                {availableSources
                  .filter((s) => s.is_builtin)
                  .map((source) => (
                    <div key={source.id}>{renderSourceItem(source)}</div>
                  ))}
              </>
            )}

            {/* User-defined sources */}
            {availableSources.filter((s) => !s.is_builtin).length > 0 && (
              <>
                <Divider />
                <Text strong style={{ marginBottom: 8, display: 'block' }}>
                  Мои источники
                </Text>
                {availableSources
                  .filter((s) => !s.is_builtin)
                  .map((source) => (
                    <div key={source.id}>{renderSourceItem(source)}</div>
                  ))}
              </>
            )}

            {availableSources.length === 0 && (
              <Alert
                message="Нет доступных источников"
                description="У вашей компании пока нет настроенных источников законодательства."
                type="info"
                showIcon
              />
            )}

            <Divider />

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text type="secondary">
                Выбрано источников: {selectedSources.length} из {availableSources.length}
              </Text>
              <Button
                type="primary"
                icon={<SaveOutlined />}
                onClick={handleSaveSources}
                loading={saving}
                size="large"
              >
                Сохранить источники
              </Button>
            </div>
          </Space>
        </Card>
      ),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <Breadcrumb
        items={[
          { title: <span onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>Главная</span> },
          { title: profile ? `${profile.legal_form} ${profile.name}` : 'Профиль компании' },
        ]}
        style={{ marginBottom: 16 }}
      />

      <Button
        type="link"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/')}
        style={{ padding: 0, marginBottom: 16 }}
      >
        На главную
      </Button>

      <Title level={3} style={{ marginBottom: 4 }}>
        {profile ? `${profile.legal_form} "${profile.name}"` : 'Профиль компании'}
      </Title>
      {profile?.inn && (
        <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
          ИНН: {profile.inn}
        </Text>
      )}

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={tabItems}
        style={{ marginTop: 8 }}
      />
    </div>
  )
}
