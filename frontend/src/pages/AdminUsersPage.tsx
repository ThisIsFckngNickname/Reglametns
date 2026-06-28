import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
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
  message,
  Tabs,
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined, UserOutlined, LockOutlined, UnlockOutlined, SwapOutlined, InfoCircleOutlined } from '@ant-design/icons'
import { getAdminUsers, createAdminUser, updateAdminUser, deleteAdminUser, banUser, unbanUser, setUserCompanyRole } from '../api/admin'
import { getCompanies } from '../api/companies'
import { getApiErrorMessage } from '../api/client'
import type { AdminUserResponse, Company } from '../types'
import dayjs from 'dayjs'

const { Title } = Typography

const ROLE_INFO: { value: string; label: string; color: string; description: string }[] = [
  { value: 'admin', label: 'Администратор', color: 'red', description: 'Полный доступ: создание, редактирование, удаление, управление пользователями и компаниями, любые статусы документов' },
  { value: 'editor', label: 'Редактор', color: 'blue', description: 'Создание и редактирование документов, смена статусов' },
  { value: 'viewer', label: 'Просмотр', color: 'default', description: 'Только просмотр и скачивание документов' },
]

export default function AdminUsersPage() {
  const navigate = useNavigate()
  const [users, setUsers] = useState<AdminUserResponse[]>([])
  const [companies, setCompanies] = useState<Company[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<AdminUserResponse | null>(null)
  const [modalLoading, setModalLoading] = useState(false)
  const [modalError, setModalError] = useState<string | null>(null)
  const [form] = Form.useForm()

  const [roleModalOpen, setRoleModalOpen] = useState(false)
  const [roleModalUser, setRoleModalUser] = useState<AdminUserResponse | null>(null)
  const [roleModalLoading, setRoleModalLoading] = useState(false)
  const [roleModalError, setRoleModalError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [usersData, companiesData] = await Promise.all([
        getAdminUsers(),
        getCompanies(),
      ])
      setUsers(usersData)
      setCompanies(companiesData)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const openCreateModal = () => {
    setEditingUser(null)
    form.resetFields()
    setModalError(null)
    setModalOpen(true)
  }

  const openEditModal = (user: AdminUserResponse) => {
    setEditingUser(user)
    form.setFieldsValue({
      email: user.email,
      is_verified: user.is_verified,
    })
    setModalError(null)
    setModalOpen(true)
  }

  const handleModalOk = async () => {
    try {
      const values = await form.validateFields()
      setModalLoading(true)
      setModalError(null)

      if (editingUser) {
        const updateData: Record<string, unknown> = {}
        if (values.email !== editingUser.email) updateData.email = values.email
        if (values.password) updateData.password = values.password
        if (values.is_verified !== undefined) updateData.is_verified = values.is_verified
        await updateAdminUser(editingUser.id, updateData)
        message.success('Пользователь обновлён')
      } else {
        await createAdminUser({
          email: values.email,
          password: values.password,
          company_id: values.company_id || null,
          role: values.role || 'user',
        })
        message.success('Пользователь создан')
      }

      setModalOpen(false)
      await loadData()
    } catch (err) {
      if (err instanceof Error && 'errorFields' in err) return
      setModalError(getApiErrorMessage(err))
    } finally {
      setModalLoading(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteAdminUser(id)
      message.success('Пользователь удалён')
      await loadData()
    } catch (err) {
      setError(getApiErrorMessage(err))
    }
  }

  const handleBan = async (id: number) => {
    try {
      await banUser(id)
      message.success('Пользователь заблокирован')
      await loadData()
    } catch (err) {
      setError(getApiErrorMessage(err))
    }
  }

  const handleUnban = async (id: number) => {
    try {
      await unbanUser(id)
      message.success('Пользователь разблокирован')
      await loadData()
    } catch (err) {
      setError(getApiErrorMessage(err))
    }
  }

  const handleRoleChange = async (userId: number, companyId: number, role: string) => {
    try {
      setRoleModalLoading(true)
      await setUserCompanyRole(userId, companyId, role)
      message.success('Роль обновлена')
      setRoleModalError(null)
      await loadData()
    } catch (err) {
      setRoleModalError(getApiErrorMessage(err))
    } finally {
      setRoleModalLoading(false)
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
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
    },
    {
      title: 'Статус',
      dataIndex: 'is_verified',
      key: 'is_verified',
      width: 100,
      render: (_: boolean, record: AdminUserResponse) => (
        <Space>
          {record.is_banned ? (
            <Tag color="red">Заблокирован</Tag>
          ) : record.is_verified ? (
            <Tag color="green">Подтверждён</Tag>
          ) : (
            <Tag color="orange">Не подтверждён</Tag>
          )}
        </Space>
      ),
    },
    {
      title: 'Компании / Роль',
      key: 'companies',
      width: 320,
      render: (_: unknown, record: AdminUserResponse) => (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
          {record.companies.length > 0
            ? record.companies.map((h) => (
                <div key={h.company_id} style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'nowrap' }}>
                  <Tag style={{ margin: 0, whiteSpace: 'nowrap' }} color={h.role === 'admin' ? 'red' : h.role === 'editor' || h.role === 'member' ? 'blue' : 'default'}>
                    {h.company_name}
                  </Tag>
                  <Select
                    size="small"
                    value={h.role}
                    style={{ width: 130 }}
                    onChange={(newRole) => handleRoleChange(record.id, h.company_id, newRole)}
                    options={ROLE_INFO.map(r => ({ value: r.value, label: r.label }))}
                  />
                </div>
              ))
            : <Tag>Нет компаний</Tag>}
        </div>
      ),
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
      width: 160,
      render: (_: unknown, record: AdminUserResponse) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => openEditModal(record)}
          >
            Ред.
          </Button>
          {record.is_banned ? (
            <Popconfirm
              title="Разблокировать пользователя?"
              onConfirm={() => handleUnban(record.id)}
              okText="Разблокировать"
              cancelText="Отмена"
            >
              <Button type="link" icon={<UnlockOutlined />}>
                Разблокировать
              </Button>
            </Popconfirm>
          ) : (
            <Popconfirm
              title="Заблокировать пользователя?"
              description="Пользователь не сможет войти в систему"
              onConfirm={() => handleBan(record.id)}
              okText="Заблокировать"
              cancelText="Отмена"
            >
              <Button type="link" danger icon={<LockOutlined />}>
                Заблокировать
              </Button>
            </Popconfirm>
          )}
          <Popconfirm
            title="Удалить пользователя?"
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
          activeKey="users"
          onChange={(key) => {
            if (key === 'companies') navigate('/admin/companies')
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
              <UserOutlined style={{ marginRight: 8 }} />
              Управление пользователями
            </Title>
            <Space>
              <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading}>
                Обновить
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={openCreateModal}
              >
                Создать пользователя
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

          {/* Role permissions legend */}
          <Card size="small" title={<Space><InfoCircleOutlined />Права ролей</Space>} style={{ marginBottom: 16 }}>
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              {ROLE_INFO.map((r) => (
                <div key={r.value} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <Tag color={r.color} style={{ width: 140, textAlign: 'center', margin: 0 }}>
                    {r.label}
                  </Tag>
                  <span style={{ color: '#595959', fontSize: 13 }}>{r.description}</span>
                </div>
              ))}
            </Space>
          </Card>

          <Table
            columns={columns}
            dataSource={users}
            rowKey="id"
            loading={loading}
            pagination={false}
            scroll={{ x: 'max-content' }}
          />
        </Space>
      </Card>

      {/* Create/Edit Modal */}
      <Modal
        title={editingUser ? 'Редактировать пользователя' : 'Создать пользователя'}
        open={modalOpen}
        onOk={handleModalOk}
        onCancel={() => setModalOpen(false)}
        confirmLoading={modalLoading}
        okText={editingUser ? 'Сохранить' : 'Создать'}
        cancelText="Отмена"
        destroyOnClose
        width={520}
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
            name="email"
            label="Email"
            rules={[
              { required: true, message: 'Введите email' },
              { type: 'email', message: 'Некорректный email' },
            ]}
          >
            <Input placeholder="user@example.com" />
          </Form.Item>

          <Form.Item
            name="password"
            label="Пароль"
            rules={
              editingUser
                ? []
                : [{ required: true, message: 'Введите пароль' }, { min: 6, message: 'Минимум 6 символов' }]
            }
          >
            <Input.Password
              placeholder={editingUser ? 'Оставьте пустым, чтобы не менять' : 'Придумайте пароль'}
            />
          </Form.Item>

          {!editingUser && (
            <>
              <Form.Item name="company_id" label="Компания">
                <Select
                  placeholder="Выберите компанию (опционально)"
                  allowClear
                  options={companies.map((h) => ({
                    value: h.id,
                    label: `${h.legal_form} "${h.name}"`,
                  }))}
                />
              </Form.Item>

              <Form.Item name="role" label="Роль" initialValue="editor">
                <Select
                  options={ROLE_INFO.map(r => ({ value: r.value, label: r.label }))}
                />
              </Form.Item>
            </>
          )}

          {editingUser && (
            <Form.Item name="is_verified" label="Статус" initialValue={true}>
              <Select
                options={[
                  { value: true, label: 'Подтверждён' },
                  { value: false, label: 'Не подтверждён' },
                ]}
              />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </div>
  )
}
