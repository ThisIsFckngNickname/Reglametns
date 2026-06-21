import { useEffect, useState } from 'react'
import {
  Card,
  Typography,
  Select,
  Button,
  Alert,
  Space,
  Spin,
  Descriptions,
  Tag,
} from 'antd'
import { useNavigate } from 'react-router-dom'
import { getCurrentUser } from '../api/auth'
import { getCompanies, setActiveCompany } from '../api/companies'
import { getApiErrorMessage } from '../api/client'
import { useAuthStore } from '../store/authStore'
import type { Company } from '../types'

const { Title, Text } = Typography

export default function ProfilePage() {
  const navigate = useNavigate()
  const { user, updateUser } = useAuthStore()
  const [companies, setCompanies] = useState<Company[]>([])
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [companiesData, userData] = await Promise.all([
        getCompanies(),
        getCurrentUser(),
      ])
      updateUser(userData)
      
      // Показываем только те компании, в которых пользователь состоит
      const userCompanyIds = new Set(userData.companies?.map(h => h.company_id) ?? [])
      const filtered = companiesData.filter(h => userCompanyIds.has(h.id))
      setCompanies(filtered)
      
      if (userData.active_company) {
        setSelectedCompanyId(userData.active_company.id)
      }
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const handleSelectCompany = async (companyId: number) => {
    setSaving(true)
    setError(null)
    setSuccess(false)

    try {
      const result = await setActiveCompany({ company_id: companyId })
      updateUser({
        active_company: {
          id: companyId,
          name: result.active_company.name,
          inn: null,
          legal_form: '',
        },
      })
      setSelectedCompanyId(companyId)
      setSuccess(true)

      // Navigate to dashboard after selection
      setTimeout(() => {
        navigate('/')
      }, 1500)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}>
        <Spin size="large" tip="Загрузка профиля..." />
      </div>
    )
  }

  const userCompanyLabel = (company: Company) =>
    `${company.legal_form} "${company.name}"${company.inn ? ` ИНН: ${company.inn}` : ''}`

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', paddingTop: 40 }}>
      <Card>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Title level={3}>Профиль пользователя</Title>

          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="Email">{user?.email}</Descriptions.Item>
            <Descriptions.Item label="Статус">
              {user?.is_verified ? (
                <Tag color="green">Подтверждён</Tag>
              ) : (
                <Tag color="orange">Не подтверждён</Tag>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="Текущая компания">
              {user?.active_company ? (
                <Text strong>
                  {user.active_company.legal_form} &quot;{user.active_company.name}
                  &quot;
                  {user.active_company.inn && ` ИНН: ${user.active_company.inn}`}
                </Text>
              ) : (
                <Text type="secondary">Не выбрана</Text>
              )}
            </Descriptions.Item>
          </Descriptions>

          <div>
            <Title level={5}>Выбор компании</Title>
            <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
              Выберите компанию для работы с документами
            </Text>

            {error && (
              <Alert
                message="Ошибка"
                description={error}
                type="error"
                showIcon
                closable
                onClose={() => setError(null)}
                style={{ marginBottom: 12 }}
              />
            )}

            {success && (
              <Alert
                message="Компания выбрана"
                description="Компания успешно установлена. Перенаправляем на дашборд..."
                type="success"
                showIcon
                style={{ marginBottom: 12 }}
              />
            )}

            <Space direction="vertical" style={{ width: '100%' }}>
              <Select
                style={{ width: '100%' }}
                placeholder="Выберите компанию"
                loading={loading}
                value={selectedCompanyId}
                onChange={setSelectedCompanyId}
                options={companies.map((h) => ({
                  value: h.id,
                  label: userCompanyLabel(h),
                }))}
                showSearch
                optionFilterProp="label"
                size="large"
              />
              <Button
                type="primary"
                block
                size="large"
                loading={saving}
                disabled={!selectedCompanyId || selectedCompanyId === user?.active_company?.id}
                onClick={() => selectedCompanyId && handleSelectCompany(selectedCompanyId)}
              >
                {user?.active_company ? 'Сменить компанию' : 'Выбрать компанию'}
              </Button>
            </Space>
          </div>
        </Space>
      </Card>
    </div>
  )
}
