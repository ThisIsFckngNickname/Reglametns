import { useEffect, useState, useCallback } from 'react'
import {
  Card,
  Typography,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  Alert,
  Space,
  Popconfirm,
  Tag,
  Tabs,
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined, ProfileOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { getCompanies, createCompany, updateCompany, deleteCompany } from '../api/companies'
import { getApiErrorMessage } from '../api/client'
import type { Company, CompanyCreate, CompanyUpdate } from '../types'
import dayjs from 'dayjs'

const { Title } = Typography

const LEGAL_FORM_OPTIONS = [
  { value: 'ООО', label: 'ООО' },
  { value: 'АО', label: 'АО' },
  { value: 'ПАО', label: 'ПАО' },
  { value: 'иное', label: 'Иное' },
]

export default function AdminCompaniesPage() {
  const navigate = useNavigate()
  const [companies, setCompanies] = useState<Company[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [editingCompany, setEditingCompany] = useState<Company | null>(null)
  const [modalLoading, setModalLoading] = useState(false)
  const [modalError, setModalError] = useState<string | null>(null)
  const [form] = Form.useForm()

  const loadCompanies = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getCompanies()
      setCompanies(data)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadCompanies()
  }, [loadCompanies])

  const openCreateModal = () => {
    setEditingCompany(null)
    form.resetFields()
    setModalError(null)
    setModalOpen(true)
  }

  const openEditModal = (company: Company) => {
    setEditingCompany(company)
    form.setFieldsValue({
      name: company.name,
      inn: company.inn,
      legal_form: company.legal_form,
    })
    setModalError(null)
    setModalOpen(true)
  }

  const handleModalOk = async () => {
    try {
      const values = await form.validateFields()
      setModalLoading(true)
      setModalError(null)

      if (editingCompany) {
        const updateData: CompanyUpdate = {}
        if (values.name !== editingCompany.name) updateData.name = values.name
        if (values.inn !== editingCompany.inn) updateData.inn = values.inn || null
        if (values.legal_form !== editingCompany.legal_form) updateData.legal_form = values.legal_form
        await updateCompany(editingCompany.id, updateData)
      } else {
        await createCompany(values as CompanyCreate)
      }

      setModalOpen(false)
      await loadCompanies()
    } catch (err) {
      if (err instanceof Error && 'errorFields' in err) return // validation error
      setModalError(getApiErrorMessage(err))
    } finally {
      setModalLoading(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteCompany(id)
      await loadCompanies()
    } catch (err) {
      setError(getApiErrorMessage(err))
    }
  }

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: 'Наименование',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: Company) => (
        <span>
          {record.legal_form} &quot;{name}&quot;
        </span>
      ),
    },
    {
      title: 'ИНН',
      dataIndex: 'inn',
      key: 'inn',
      render: (inn: string | null) => inn || <Tag>Не указан</Tag>,
    },
    {
      title: 'Юр. форма',
      dataIndex: 'legal_form',
      key: 'legal_form',
      width: 100,
      render: (form: string) => <Tag>{form}</Tag>,
    },
    {
      title: 'Дата создания',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (date: string) => dayjs(date).format('DD.MM.YYYY HH:mm'),
    },
    {
      title: 'Действия',
      key: 'actions',
      width: 200,
      render: (_: unknown, record: Company) => (
        <Space>
          <Button
            type="link"
            icon={<ProfileOutlined />}
            onClick={() => navigate(`/companies/${record.id}/profile`)}
          >
            Профиль
          </Button>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => openEditModal(record)}
          >
            Редакт.
          </Button>
          <Popconfirm
            title="Удалить компанию?"
            description="Это действие нельзя отменить"
            onConfirm={() => handleDelete(record.id)}
            okText="Удалить"
            cancelText="Отмена"
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              Удалить
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Card>
        <Tabs
          activeKey="companies"
          onChange={(key) => {
            if (key === 'users') navigate('/admin/users')
          }}
          items={[
            { key: 'companies', label: '🏢 Компании' },
            { key: 'users', label: '👤 Пользователи' },
          ]}
          style={{ marginBottom: 0 }}
        />
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <Title level={3} style={{ margin: 0 }}>
              Управление компаниями
            </Title>
            <Space>
              <Button icon={<ReloadOutlined />} onClick={loadCompanies} loading={loading}>
                Обновить
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={openCreateModal}
              >
                Создать компанию
              </Button>
            </Space>
          </div>

          {error && (
            <Alert
              message="Ошибка"
              description={error}
              type="error"
              showIcon
              closable
              onClose={() => setError(null)}
            />
          )}

          <Table
            columns={columns}
            dataSource={companies}
            rowKey="id"
            loading={loading}
            pagination={false}
          />
        </Space>
      </Card>

      {/* Create/Edit Modal */}
      <Modal
        title={editingCompany ? 'Редактировать компанию' : 'Создать компанию'}
        open={modalOpen}
        onOk={handleModalOk}
        onCancel={() => setModalOpen(false)}
        confirmLoading={modalLoading}
        okText={editingCompany ? 'Сохранить' : 'Создать'}
        cancelText="Отмена"
        destroyOnClose
      >
        {modalError && (
          <Alert
            message="Ошибка"
            description={modalError}
            type="error"
            showIcon
            style={{ marginBottom: 16 }}
            closable
            onClose={() => setModalError(null)}
          />
        )}

        <Form form={form} layout="vertical" preserve={false}>
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
        </Form>
      </Modal>
    </div>
  )
}
