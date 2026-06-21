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
import { getHoldings, setActiveHolding } from '../api/holdings'
import { getApiErrorMessage } from '../api/client'
import { useAuthStore } from '../store/authStore'
import type { Holding } from '../types'

const { Title, Text } = Typography

export default function ProfilePage() {
  const navigate = useNavigate()
  const { user, updateUser } = useAuthStore()
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [selectedHoldingId, setSelectedHoldingId] = useState<number | null>(null)
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
      const [holdingsData, userData] = await Promise.all([
        getHoldings(),
        getCurrentUser(),
      ])
      updateUser(userData)
      
      // Показываем только те холдинги, в которых пользователь состоит
      const userHoldingIds = new Set(userData.holdings?.map(h => h.holding_id) ?? [])
      const filtered = holdingsData.filter(h => userHoldingIds.has(h.id))
      setHoldings(filtered)
      
      if (userData.active_holding) {
        setSelectedHoldingId(userData.active_holding.id)
      }
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const handleSelectHolding = async (holdingId: number) => {
    setSaving(true)
    setError(null)
    setSuccess(false)

    try {
      const result = await setActiveHolding({ holding_id: holdingId })
      updateUser({
        active_holding: {
          id: holdingId,
          name: result.active_holding.name,
          inn: null,
          legal_form: '',
        },
      })
      setSelectedHoldingId(holdingId)
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

  const userHoldingLabel = (holding: Holding) =>
    `${holding.legal_form} "${holding.name}"${holding.inn ? ` ИНН: ${holding.inn}` : ''}`

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
            <Descriptions.Item label="Текущий холдинг">
              {user?.active_holding ? (
                <Text strong>
                  {user.active_holding.legal_form} &quot;{user.active_holding.name}
                  &quot;
                  {user.active_holding.inn && ` ИНН: ${user.active_holding.inn}`}
                </Text>
              ) : (
                <Text type="secondary">Не выбран</Text>
              )}
            </Descriptions.Item>
          </Descriptions>

          <div>
            <Title level={5}>Выбор холдинга</Title>
            <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
              Выберите холдинг для работы с документами
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
                message="Холдинг выбран"
                description="Холдинг успешно установлен. Перенаправляем на дашборд..."
                type="success"
                showIcon
                style={{ marginBottom: 12 }}
              />
            )}

            <Space direction="vertical" style={{ width: '100%' }}>
              <Select
                style={{ width: '100%' }}
                placeholder="Выберите холдинг"
                loading={loading}
                value={selectedHoldingId}
                onChange={setSelectedHoldingId}
                options={holdings.map((h) => ({
                  value: h.id,
                  label: userHoldingLabel(h),
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
                disabled={!selectedHoldingId || selectedHoldingId === user?.active_holding?.id}
                onClick={() => selectedHoldingId && handleSelectHolding(selectedHoldingId)}
              >
                {user?.active_holding ? 'Сменить холдинг' : 'Выбрать холдинг'}
              </Button>
            </Space>
          </div>
        </Space>
      </Card>
    </div>
  )
}
