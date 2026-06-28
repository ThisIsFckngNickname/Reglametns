import { useState, useEffect, useCallback } from 'react'
import {
  Card,
  Tabs,
  Table,
  Input,
  Button,
  Space,
  Typography,
  Modal,
  Form,
  Popconfirm,
  message,
  Tag,
  Spin,
} from 'antd'
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SearchOutlined,
  BookOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useAuthStore } from '../store/authStore'
import {
  getTerms,
  createTerm,
  updateTerm,
  deleteTerm,
  getAbbreviations,
  createAbbreviation,
  updateAbbreviation,
  deleteAbbreviation,
} from '../api/companyTerms'
import type { CompanyTerm, CompanyAbbreviation } from '../types/companyTerms'

const { Title, Text } = Typography
const { TextArea } = Input

type TabKey = 'terms' | 'abbreviations'

export default function TermsPage() {
  const { user } = useAuthStore()

  // Determine if user can edit (editor+)
  const canEdit = user?.companies?.some(
    (c) =>
      c.company_id === user.active_company?.id &&
      (c.role === 'editor' || c.role === 'admin' || c.role === 'member')
  )

  // ─── Active tab ────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState<TabKey>('terms')

  // ─── Terms state ───────────────────────────────────────────────────
  const [terms, setTerms] = useState<CompanyTerm[]>([])
  const [termsTotal, setTermsTotal] = useState(0)
  const [termsPage, setTermsPage] = useState(1)
  const [termsPageSize] = useState(20)
  const [termsSearch, setTermsSearch] = useState('')
  const [termsLoading, setTermsLoading] = useState(false)

  // ─── Abbreviations state ──────────────────────────────────────────
  const [abbreviations, setAbbreviations] = useState<CompanyAbbreviation[]>([])
  const [abbrTotal, setAbbrTotal] = useState(0)
  const [abbrPage, setAbbrPage] = useState(1)
  const [abbrPageSize] = useState(20)
  const [abbrSearch, setAbbrSearch] = useState('')
  const [abbrLoading, setAbbrLoading] = useState(false)

  // ─── Modal state ───────────────────────────────────────────────────
  const [modalOpen, setModalOpen] = useState(false)
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create')
  const [editingItem, setEditingItem] = useState<CompanyTerm | CompanyAbbreviation | null>(null)
  const [modalLoading, setModalLoading] = useState(false)

  const [form] = Form.useForm()

  // ─── Data fetching ─────────────────────────────────────────────────
  const fetchTerms = useCallback(async (page: number, q: string) => {
    setTermsLoading(true)
    try {
      const res = await getTerms({ page, page_size: termsPageSize, q: q || undefined })
      setTerms(res.items)
      setTermsTotal(res.total)
      setTermsPage(res.page)
    } catch {
      message.error('Не удалось загрузить термины')
    } finally {
      setTermsLoading(false)
    }
  }, [termsPageSize])

  const fetchAbbreviations = useCallback(async (page: number, q: string) => {
    setAbbrLoading(true)
    try {
      const res = await getAbbreviations({ page, page_size: abbrPageSize, q: q || undefined })
      setAbbreviations(res.items)
      setAbbrTotal(res.total)
      setAbbrPage(res.page)
    } catch {
      message.error('Не удалось загрузить сокращения')
    } finally {
      setAbbrLoading(false)
    }
  }, [abbrPageSize])

  useEffect(() => {
    if (activeTab === 'terms') {
      fetchTerms(termsPage, termsSearch)
    }
  }, [activeTab, termsPage, termsSearch, fetchTerms])

  useEffect(() => {
    if (activeTab === 'abbreviations') {
      fetchAbbreviations(abbrPage, abbrSearch)
    }
  }, [activeTab, abbrPage, abbrSearch, fetchAbbreviations])

  // ─── Search handlers ───────────────────────────────────────────────
  const handleTermsSearch = useCallback((value: string) => {
    setTermsSearch(value)
    setTermsPage(1)
  }, [])

  const handleAbbrSearch = useCallback((value: string) => {
    setAbbrSearch(value)
    setAbbrPage(1)
  }, [])

  // ─── Modal handlers ────────────────────────────────────────────────
  const openCreateModal = useCallback(() => {
    setModalMode('create')
    setEditingItem(null)
    form.resetFields()
    setModalOpen(true)
  }, [form])

  const openEditModal = useCallback((item: CompanyTerm | CompanyAbbreviation) => {
    setModalMode('edit')
    setEditingItem(item)
    if (activeTab === 'terms') {
      const t = item as CompanyTerm
      form.setFieldsValue({ term: t.term, definition: t.definition })
    } else {
      const a = item as CompanyAbbreviation
      form.setFieldsValue({ abbreviation: a.abbreviation, full_form: a.full_form })
    }
    setModalOpen(true)
  }, [activeTab, form])

  const handleModalCancel = useCallback(() => {
    setModalOpen(false)
    setEditingItem(null)
    form.resetFields()
  }, [form])

  const handleModalSubmit = useCallback(async () => {
    try {
      const values = await form.validateFields()
      setModalLoading(true)

      if (activeTab === 'terms') {
        if (modalMode === 'create') {
          await createTerm({ term: values.term, definition: values.definition })
          message.success('Термин создан')
        } else {
          const updateData: { term?: string; definition?: string } = {}
          if (values.term !== (editingItem as CompanyTerm)?.term) updateData.term = values.term
          if (values.definition !== (editingItem as CompanyTerm)?.definition) updateData.definition = values.definition
          if (Object.keys(updateData).length > 0) {
            await updateTerm(editingItem!.id, updateData)
          }
          message.success('Термин обновлён')
        }
      } else {
        if (modalMode === 'create') {
          await createAbbreviation({ abbreviation: values.abbreviation, full_form: values.full_form })
          message.success('Сокращение создано')
        } else {
          const updateData: { abbreviation?: string; full_form?: string } = {}
          if (values.abbreviation !== (editingItem as CompanyAbbreviation)?.abbreviation) updateData.abbreviation = values.abbreviation
          if (values.full_form !== (editingItem as CompanyAbbreviation)?.full_form) updateData.full_form = values.full_form
          if (Object.keys(updateData).length > 0) {
            await updateAbbreviation(editingItem!.id, updateData)
          }
          message.success('Сокращение обновлено')
        }
      }

      setModalOpen(false)
      setEditingItem(null)
      form.resetFields()

      // Refresh current tab
      if (activeTab === 'terms') {
        fetchTerms(termsPage, termsSearch)
      } else {
        fetchAbbreviations(abbrPage, abbrSearch)
      }
    } catch (err: any) {
      if (err?.response?.data?.detail?.message) {
        message.error(err.response.data.detail.message)
      } else if (err?.errorFields) {
        // Validation error from form — do nothing, form shows errors
      } else {
        message.error('Ошибка при сохранении')
      }
    } finally {
      setModalLoading(false)
    }
  }, [activeTab, modalMode, editingItem, form, termsPage, termsSearch, abbrPage, abbrSearch, fetchTerms, fetchAbbreviations])

  // ─── Delete handlers ───────────────────────────────────────────────
  const handleDeleteTerm = useCallback(async (id: number) => {
    try {
      await deleteTerm(id)
      message.success('Термин удалён')
      fetchTerms(termsPage, termsSearch)
    } catch {
      message.error('Не удалось удалить термин')
    }
  }, [termsPage, termsSearch, fetchTerms])

  const handleDeleteAbbreviation = useCallback(async (id: number) => {
    try {
      await deleteAbbreviation(id)
      message.success('Сокращение удалено')
      fetchAbbreviations(abbrPage, abbrSearch)
    } catch {
      message.error('Не удалось удалить сокращение')
    }
  }, [abbrPage, abbrSearch, fetchAbbreviations])

  // ─── Table columns ─────────────────────────────────────────────────
  const termColumns: ColumnsType<CompanyTerm> = [
    {
      title: 'Термин',
      dataIndex: 'term',
      key: 'term',
      width: '20%',
      render: (text: string) => <Text strong>{text}</Text>,
    },
    {
      title: 'Определение',
      dataIndex: 'definition',
      key: 'definition',
      width: '40%',
    },
    {
      title: 'Источник',
      dataIndex: 'source_document_title',
      key: 'source',
      width: '20%',
      render: (title: string | null) =>
        title ? <Text>{title}</Text> : <Text type="secondary">—</Text>,
    },
    {
      title: 'Действия',
      key: 'actions',
      width: '20%',
      render: (_: unknown, record: CompanyTerm) =>
        canEdit ? (
          <Space>
            <Button
              type="link"
              icon={<EditOutlined />}
              onClick={() => openEditModal(record)}
            >
              Редактировать
            </Button>
            <Popconfirm
              title="Вы уверены?"
              description="Термин будет удалён из общехолдингового перечня"
              onConfirm={() => handleDeleteTerm(record.id)}
              okText="Удалить"
              cancelText="Отмена"
              okButtonProps={{ danger: true }}
            >
              <Button type="link" danger icon={<DeleteOutlined />}>
                Удалить
              </Button>
            </Popconfirm>
          </Space>
        ) : null,
    },
  ]

  const abbreviationColumns: ColumnsType<CompanyAbbreviation> = [
    {
      title: 'Сокращение',
      dataIndex: 'abbreviation',
      key: 'abbreviation',
      width: '20%',
      render: (text: string) => <Text strong>{text}</Text>,
    },
    {
      title: 'Расшифровка',
      dataIndex: 'full_form',
      key: 'full_form',
      width: '40%',
    },
    {
      title: 'Источник',
      dataIndex: 'source_document_title',
      key: 'source',
      width: '20%',
      render: (title: string | null) =>
        title ? <Text>{title}</Text> : <Text type="secondary">—</Text>,
    },
    {
      title: 'Действия',
      key: 'actions',
      width: '20%',
      render: (_: unknown, record: CompanyAbbreviation) =>
        canEdit ? (
          <Space>
            <Button
              type="link"
              icon={<EditOutlined />}
              onClick={() => openEditModal(record)}
            >
              Редактировать
            </Button>
            <Popconfirm
              title="Вы уверены?"
              description="Сокращение будет удалено из общехолдингового перечня"
              onConfirm={() => handleDeleteAbbreviation(record.id)}
              okText="Удалить"
              cancelText="Отмена"
              okButtonProps={{ danger: true }}
            >
              <Button type="link" danger icon={<DeleteOutlined />}>
                Удалить
              </Button>
            </Popconfirm>
          </Space>
        ) : null,
    },
  ]

  // ─── Tab items ─────────────────────────────────────────────────────
  const tabItems = [
    {
      key: 'terms',
      label: (
        <span>
          <BookOutlined /> Термины
        </span>
      ),
      children: (
        <div>
          <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
            <Input.Search
              placeholder="Поиск терминов..."
              allowClear
              onSearch={handleTermsSearch}
              style={{ width: 320 }}
              enterButton={<SearchOutlined />}
            />
            {canEdit && (
              <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
                Добавить термин
              </Button>
            )}
          </Space>

          <Table
            columns={termColumns}
            dataSource={terms}
            rowKey="id"
            loading={termsLoading}
            pagination={{
              current: termsPage,
              pageSize: termsPageSize,
              total: termsTotal,
              showTotal: (total, range) => `${range[0]}–${range[1]} из ${total}`,
              onChange: (page) => setTermsPage(page),
            }}
            locale={{ emptyText: 'Термины не найдены' }}
          />
        </div>
      ),
    },
    {
      key: 'abbreviations',
      label: (
        <span>
          <BookOutlined /> Сокращения
        </span>
      ),
      children: (
        <div>
          <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
            <Input.Search
              placeholder="Поиск сокращений..."
              allowClear
              onSearch={handleAbbrSearch}
              style={{ width: 320 }}
              enterButton={<SearchOutlined />}
            />
            {canEdit && (
              <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
                Добавить сокращение
              </Button>
            )}
          </Space>

          <Table
            columns={abbreviationColumns}
            dataSource={abbreviations}
            rowKey="id"
            loading={abbrLoading}
            pagination={{
              current: abbrPage,
              pageSize: abbrPageSize,
              total: abbrTotal,
              showTotal: (total, range) => `${range[0]}–${range[1]} из ${total}`,
              onChange: (page) => setAbbrPage(page),
            }}
            locale={{ emptyText: 'Сокращения не найдены' }}
          />
        </div>
      ),
    },
  ]

  // ─── Modal title ───────────────────────────────────────────────────
  const getModalTitle = () => {
    const prefix = modalMode === 'create' ? 'Создание' : 'Редактирование'
    const entity = activeTab === 'terms' ? 'термина' : 'сокращения'
    return `${prefix} ${entity}`
  }

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto' }}>
      <Title level={3} style={{ marginBottom: 24 }}>
        <BookOutlined style={{ marginRight: 8 }} />
        Термины и сокращения холдинга
      </Title>

      <Card bodyStyle={{ padding: 0 }}>
        <Tabs
          activeKey={activeTab}
          onChange={(key) => {
            setActiveTab(key as TabKey)
            form.resetFields()
          }}
          items={tabItems}
          style={{ padding: '0 24px' }}
        />
      </Card>

      {/* Create / Edit Modal */}
      <Modal
        title={getModalTitle()}
        open={modalOpen}
        onOk={handleModalSubmit}
        onCancel={handleModalCancel}
        confirmLoading={modalLoading}
        okText="Сохранить"
        cancelText="Отмена"
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          preserve={false}
          style={{ marginTop: 16 }}
        >
          {activeTab === 'terms' ? (
            <>
              <Form.Item
                name="term"
                label="Термин"
                rules={[
                  { required: true, message: 'Введите термин' },
                  { max: 255, message: 'Максимум 255 символов' },
                ]}
              >
                <Input placeholder="Например: УК" />
              </Form.Item>
              <Form.Item
                name="definition"
                label="Определение"
                rules={[
                  { required: true, message: 'Введите определение' },
                ]}
              >
                <TextArea
                  rows={4}
                  placeholder="Введите определение термина"
                  showCount
                  maxLength={2000}
                />
              </Form.Item>
            </>
          ) : (
            <>
              <Form.Item
                name="abbreviation"
                label="Сокращение"
                rules={[
                  { required: true, message: 'Введите сокращение' },
                  { max: 50, message: 'Максимум 50 символов' },
                ]}
              >
                <Input placeholder="Например: МОЛ" />
              </Form.Item>
              <Form.Item
                name="full_form"
                label="Расшифровка"
                rules={[
                  { required: true, message: 'Введите расшифровку' },
                  { max: 500, message: 'Максимум 500 символов' },
                ]}
              >
                <TextArea
                  rows={4}
                  placeholder="Введите расшифровку сокращения"
                  showCount
                  maxLength={500}
                />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </div>
  )
}
