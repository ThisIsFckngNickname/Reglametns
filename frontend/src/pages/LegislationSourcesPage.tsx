import { useEffect, useState, useCallback } from 'react'
import {
  Breadcrumb,
  Button,
  Card,
  Drawer,
  Form,
  Input,
  Select,
  Switch,
  Table,
  Tag,
  Typography,
  Space,
  Popconfirm,
  message,
  Spin,
  List,
  Alert,
  Divider,
  Tooltip,
  Empty,
} from 'antd'
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SearchOutlined,
  LinkOutlined,
  FileTextOutlined,
  GlobalOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { LegislationSource, LegislationSourceCreate, LegislationSourceSearchResult } from '../types'
import {
  getLegislationSources,
  createLegislationSource,
  updateLegislationSource,
  deleteLegislationSource,
  searchInLegislationSource,
} from '../api/legislation'

const { Title, Text, Paragraph } = Typography
const { TextArea } = Input

type PageState = 'loading' | 'ready' | 'error'

const SOURCE_TYPE_LABELS: Record<string, string> = {
  template_url: 'URL-шаблон',
  static_list: 'Статический список',
  custom_parser: 'Свой парсер',
}

const PARSER_TYPE_LABELS: Record<string, string> = {
  html: 'HTML',
  json: 'JSON',
  xml: 'XML',
  text: 'Текст',
}

export default function LegislationSourcesPage() {
  const navigate = useNavigate()

  // ---- State ----
  const [sources, setSources] = useState<LegislationSource[]>([])
  const [pageState, setPageState] = useState<PageState>('loading')
  const [errorMessage, setErrorMessage] = useState('')

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editingSource, setEditingSource] = useState<LegislationSource | null>(null)
  const [drawerLoading, setDrawerLoading] = useState(false)
  const [form] = Form.useForm()

  // Search drawer state
  const [searchDrawerOpen, setSearchDrawerOpen] = useState(false)
  const [searchSource, setSearchSource] = useState<LegislationSource | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<LegislationSourceSearchResult[]>([])
  const [searchState, setSearchState] = useState<'idle' | 'loading' | 'results' | 'empty' | 'error' | 'paid'>('idle')
  const [searchErrorMessage, setSearchErrorMessage] = useState('')

  // ---- Load sources ----
  const loadSources = useCallback(() => {
    setPageState('loading')
    getLegislationSources()
      .then((data) => {
        setSources(data)
        setPageState('ready')
      })
      .catch((err) => {
        setErrorMessage(err?.response?.data?.detail?.message || err.message || 'Ошибка загрузки источников')
        setPageState('error')
      })
  }, [])

  useEffect(() => {
    loadSources()
  }, [loadSources])

  // ---- Drawer: Open for create ----
  const openCreateDrawer = () => {
    setEditingSource(null)
    form.resetFields()
    form.setFieldsValue({ source_type: 'template_url', is_paid: false })
    setDrawerOpen(true)
  }

  // ---- Drawer: Open for edit ----
  const openEditDrawer = (source: LegislationSource) => {
    setEditingSource(source)
    form.setFieldsValue({
      name: source.name,
      source_type: source.source_type,
      url_template: source.url_template,
      parser_type: source.parser_type,
      selector: source.selector,
      is_paid: source.is_paid,
      description: source.description,
      icon_url: source.icon_url,
    })
    setDrawerOpen(true)
  }

  // ---- Drawer: Close ----
  const closeDrawer = () => {
    setDrawerOpen(false)
    setEditingSource(null)
    form.resetFields()
  }

  // ---- Drawer: Submit ----
  const handleDrawerSubmit = async () => {
    try {
      const values = await form.validateFields()
      setDrawerLoading(true)

      if (editingSource) {
        await updateLegislationSource(editingSource.id, values as Partial<LegislationSourceCreate>)
        message.success('Источник обновлён')
      } else {
        await createLegislationSource(values as LegislationSourceCreate)
        message.success('Источник создан')
      }

      closeDrawer()
      loadSources()
    } catch (err: any) {
      if (err?.errorFields) {
        // Validation error, form will show messages
        return
      }
      const msg = err?.response?.data?.detail?.message || err.message || 'Ошибка сохранения'
      message.error(msg)
    } finally {
      setDrawerLoading(false)
    }
  }

  // ---- Delete ----
  const handleDelete = async (id: number) => {
    try {
      await deleteLegislationSource(id)
      message.success('Источник удалён')
      loadSources()
    } catch (err: any) {
      const msg = err?.response?.data?.detail?.message || err.message || 'Ошибка удаления'
      message.error(msg)
    }
  }

  // ---- Search Drawer: Open ----
  const openSearchDrawer = (source: LegislationSource) => {
    setSearchSource(source)
    setSearchQuery('')
    setSearchResults([])
    setSearchState('idle')
    setSearchErrorMessage('')
    setSearchDrawerOpen(true)
  }

  // ---- Search Drawer: Execute search ----
  const handleSearch = async () => {
    if (!searchSource || !searchQuery.trim()) return

    setSearchState('loading')
    try {
      const results = await searchInLegislationSource(searchSource.id, searchQuery.trim())

      // Check if response is a paid message
      if (Array.isArray(results) && results.length === 0 && searchSource.is_paid) {
        // The mock returns empty array for paid sources — we handle via is_paid flag
        setSearchState('paid')
        setSearchResults([])
        return
      }

      // The mock returns array directly on success
      if (Array.isArray(results)) {
        setSearchResults(results)
        setSearchState(results.length === 0 ? 'empty' : 'results')
      } else {
        // Handle the case where results might have a message property
        const data = results as any
        if (data?.message) {
          setSearchState('paid')
          setSearchResults([])
        } else {
          setSearchResults([])
          setSearchState('empty')
        }
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail?.message || err.message || 'Ошибка поиска'
      setSearchErrorMessage(msg)
      setSearchState('error')
    }
  }

  // ---- Source type label helper ----
  const getSourceTypeTag = (source: LegislationSource) => {
    const label = SOURCE_TYPE_LABELS[source.source_type] || source.source_type
    const color = source.source_type === 'template_url' ? 'blue'
      : source.source_type === 'static_list' ? 'green'
      : 'orange'
    return <Tag color={color}>{label}</Tag>
  }

  // ---- Table columns ----
  const columns = [
    {
      title: 'Название',
      dataIndex: 'name',
      key: 'name',
      render: (_: string, record: LegislationSource) => (
        <Space>
          <GlobalOutlined style={{ color: '#1890ff', fontSize: 18 }} />
          <Text strong>{record.name}</Text>
        </Space>
      ),
    },
    {
      title: 'Тип',
      dataIndex: 'source_type',
      key: 'source_type',
      render: (_: string, record: LegislationSource) => getSourceTypeTag(record),
    },
    {
      title: 'Платный',
      dataIndex: 'is_paid',
      key: 'is_paid',
      width: 80,
      render: (is_paid: boolean) =>
        is_paid ? <Tag color="gold">Да</Tag> : <Text type="secondary">Нет</Text>,
    },
    {
      title: 'Активен',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (is_active: boolean) => (
        <Tag color={is_active ? 'green' : 'default'}>{is_active ? 'Да' : 'Нет'}</Tag>
      ),
    },
    {
      title: 'Описание',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (desc: string | null) => desc || '—',
    },
    {
      title: 'Действия',
      key: 'actions',
      width: 140,
      render: (_: string, record: LegislationSource) => (
        <Space>
          <Tooltip title="Редактировать">
            <Button
              type="link"
              icon={<EditOutlined />}
              onClick={() => openEditDrawer(record)}
              aria-label="Редактировать источник"
            />
          </Tooltip>
          <Tooltip title="Поиск">
            <Button
              type="link"
              icon={<SearchOutlined />}
              onClick={() => openSearchDrawer(record)}
              aria-label="Поиск по источнику"
            />
          </Tooltip>
          <Tooltip title="Удалить">
            <Popconfirm
              title="Удалить источник?"
              description={`Вы уверены, что хотите удалить «${record.name}»?`}
              onConfirm={() => handleDelete(record.id)}
              okText="Удалить"
              cancelText="Отмена"
              okButtonProps={{ danger: true }}
            >
              <Button
                type="link"
                danger
                icon={<DeleteOutlined />}
                aria-label="Удалить источник"
              />
            </Popconfirm>
          </Tooltip>
        </Space>
      ),
    },
  ]

  // ---- Source type change handler for form ----
  const handleSourceTypeChange = (value: string) => {
    if (value !== 'template_url') {
      form.setFieldsValue({
        url_template: undefined,
        parser_type: undefined,
        selector: undefined,
      })
    }
  }

  // ---- Breadcrumb items ----
  const breadcrumbItems = [
    {
      title: (
        <span onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
          Главная
        </span>
      ),
    },
    {
      title: (
        <span onClick={() => navigate('/legislation')} style={{ cursor: 'pointer' }}>
          Поиск законодательства
        </span>
      ),
    },
    {
      title: 'Источники законодательства',
    },
  ]

  // ---- Loading state ----
  if (pageState === 'loading') {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '80px 0' }}>
        <Spin size="large" tip="Загрузка источников..." />
      </div>
    )
  }

  // ---- Error state ----
  if (pageState === 'error') {
    return (
      <div style={{ padding: 24 }}>
        <Breadcrumb items={breadcrumbItems} style={{ marginBottom: 16 }} />
        <Alert
          message="Ошибка загрузки"
          description={errorMessage}
          type="error"
          showIcon
          action={
            <Button onClick={loadSources} size="small">
              Повторить
            </Button>
          }
        />
      </div>
    )
  }

  return (
    <div style={{ padding: 24 }}>
      {/* Breadcrumbs */}
      <Breadcrumb items={breadcrumbItems} style={{ marginBottom: 16 }} />

      <Button
        type="link"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/legislation')}
        style={{ padding: 0, marginBottom: 16 }}
      >
        К поиску законодательства
      </Button>

      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
        }}
      >
        <div>
          <Title level={3} style={{ marginBottom: 4 }}>
            <GlobalOutlined style={{ marginRight: 8 }} />
            Источники законодательства
          </Title>
          <Paragraph type="secondary" style={{ marginBottom: 0 }}>
            Управление источниками нормативных правовых актов
          </Paragraph>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateDrawer} size="large">
          + Добавить источник
        </Button>
      </div>

      {/* Table */}
      <Card>
        <Table
          dataSource={sources}
          columns={columns}
          rowKey="id"
          pagination={false}
          locale={{ emptyText: 'Нет источников законодательства' }}
          onRow={(record) => ({
            onClick: () => openEditDrawer(record),
            style: { cursor: 'pointer' },
          })}
        />
      </Card>

      {/* Create / Edit Drawer */}
      <Drawer
        title={editingSource ? 'Редактировать источник' : 'Добавить источник'}
        open={drawerOpen}
        onClose={closeDrawer}
        width={520}
        extra={
          <Space>
            <Button onClick={closeDrawer}>Отмена</Button>
            <Button type="primary" loading={drawerLoading} onClick={handleDrawerSubmit}>
              {editingSource ? 'Сохранить' : 'Создать'}
            </Button>
          </Space>
        }
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ source_type: 'template_url', is_paid: false }}
          onClick={(e) => e.stopPropagation()}
        >
          <Form.Item
            name="name"
            label="Название"
            rules={[{ required: true, message: 'Введите название источника' }]}
          >
            <Input placeholder="Например: Pravo.gov.ru" />
          </Form.Item>

          <Form.Item
            name="source_type"
            label="Тип источника"
            rules={[{ required: true, message: 'Выберите тип источника' }]}
          >
            <Select
              placeholder="Выберите тип"
              onChange={handleSourceTypeChange}
              options={[
                { value: 'template_url', label: 'URL-шаблон' },
                { value: 'static_list', label: 'Статический список' },
                { value: 'custom_parser', label: 'Свой парсер' },
              ]}
            />
          </Form.Item>

          {/* Conditional fields for template_url */}
          <Form.Item
            noStyle
            shouldUpdate={(prev, curr) => prev.source_type !== curr.source_type}
          >
            {({ getFieldValue }) =>
              getFieldValue('source_type') === 'template_url' ? (
                <>
                  <Form.Item
                    name="url_template"
                    label="URL-шаблон"
                    tooltip="Используйте {query} как плейсхолдер для поискового запроса"
                  >
                    <Input placeholder="https://example.com/search?q={query}" />
                  </Form.Item>

                  <Form.Item name="parser_type" label="Тип парсера">
                    <Select
                      placeholder="Выберите тип парсера"
                      allowClear
                      options={[
                        { value: 'html', label: 'HTML' },
                        { value: 'json', label: 'JSON' },
                        { value: 'xml', label: 'XML' },
                        { value: 'text', label: 'Текст' },
                      ]}
                    />
                  </Form.Item>

                  <Form.Item
                    name="selector"
                    label="CSS-селектор / JSON-path"
                    tooltip="Селектор для поиска элементов в ответе"
                  >
                    <Input placeholder=".search-result или $.items[*]" />
                  </Form.Item>
                </>
              ) : null
            }
          </Form.Item>

          <Form.Item name="description" label="Описание">
            <TextArea rows={3} placeholder="Описание источника (опционально)" />
          </Form.Item>

          <Form.Item name="icon_url" label="URL иконки">
            <Input placeholder="https://example.com/icon.png (опционально)" />
          </Form.Item>

          <Form.Item name="is_paid" label="Платный источник" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Drawer>

      {/* Search Drawer */}
      <Drawer
        title={
          <Space>
            <SearchOutlined />
            Поиск: {searchSource?.name || ''}
          </Space>
        }
        open={searchDrawerOpen}
        onClose={() => {
          setSearchDrawerOpen(false)
          setSearchSource(null)
        }}
        width={560}
        destroyOnClose
      >
        {searchSource?.is_paid && (
          <Alert
            message="Платный источник"
            description="Для поиска по этому источнику требуется подписка."
            type="warning"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        <Space.Compact style={{ width: '100%', marginBottom: 16 }}>
          <Input
            placeholder="Введите поисковый запрос..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onPressEnter={handleSearch}
            disabled={searchSource?.is_paid}
            aria-label="Поисковый запрос"
          />
          <Button
            type="primary"
            icon={<SearchOutlined />}
            onClick={handleSearch}
            loading={searchState === 'loading'}
            disabled={searchSource?.is_paid || !searchQuery.trim()}
          >
            Поиск
          </Button>
        </Space.Compact>

        <Divider />

        {/* Search results */}
        {searchState === 'idle' && (
          <Empty
            description="Введите запрос и нажмите «Поиск»"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        )}

        {searchState === 'loading' && (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Spin size="large" tip="Поиск..." />
          </div>
        )}

        {searchState === 'paid' && (
          <Alert
            message="Требуется подписка"
            description="Поиск по платным источникам недоступен без активной подписки."
            type="warning"
            showIcon
          />
        )}

        {searchState === 'empty' && (
          <Empty
            description={`По запросу «${searchQuery}» ничего не найдено.`}
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        )}

        {searchState === 'error' && (
          <Alert message="Ошибка поиска" description={searchErrorMessage} type="error" showIcon />
        )}

        {searchState === 'results' && (
          <>
            <Text type="secondary" style={{ marginBottom: 12, display: 'block' }}>
              Найдено: {searchResults.length} результатов по запросу «{searchQuery}»
            </Text>

            <List
              dataSource={searchResults}
              rowKey={(item: LegislationSourceSearchResult) => `${item.url}-${item.title}`}
              renderItem={(item: LegislationSourceSearchResult) => (
                <List.Item>
                  <Card size="small" style={{ width: '100%' }} hoverable>
                    <Space align="start" direction="vertical" style={{ width: '100%' }}>
                      <Space>
                        <FileTextOutlined style={{ color: '#1890ff' }} />
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ fontWeight: 500 }}
                        >
                          {item.title}
                        </a>
                      </Space>

                      {item.date && (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {item.date}
                        </Text>
                      )}

                      <Paragraph
                        type="secondary"
                        ellipsis={{ rows: 2 }}
                        style={{ marginBottom: 0, fontSize: 13 }}
                      >
                        {item.snippet}
                      </Paragraph>

                      <Button
                        type="link"
                        icon={<LinkOutlined />}
                        href={item.url}
                        target="_blank"
                        size="small"
                        style={{ padding: 0 }}
                      >
                        Открыть
                      </Button>
                    </Space>
                  </Card>
                </List.Item>
              )}
            />
          </>
        )}
      </Drawer>
    </div>
  )
}
