import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Space, Typography, Modal, Input, Select } from 'antd'
import { SwapOutlined, LockOutlined } from '@ant-design/icons'
import { loginUser, getCurrentUser } from '../api/auth'
import { getAdminUsers } from '../api/admin'
import { useAuthStore } from '../store/authStore'
import type { AdminUserResponse } from '../types'

const { Text } = Typography

const ADMIN_EMAIL = 'admin@gmail.com'

export default function DevUserSwitcher() {
  const navigate = useNavigate()
  const setTokens = useAuthStore((s) => s.setTokens)
  const [loading, setLoading] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [users, setUsers] = useState<AdminUserResponse[]>([])
  const [selectedEmail, setSelectedEmail] = useState<string | null>(null)
  const [showUserSelect, setShowUserSelect] = useState(false)
  const [passwordModal, setPasswordModal] = useState<{ email: string; label: string } | null>(null)
  const [password, setPassword] = useState('')
  const [passwordError, setPasswordError] = useState('')

  useEffect(() => {
    if (showUserSelect) {
      getAdminUsers()
        .then((fetched) => {
          const nonAdmin = fetched.filter((u) =>
            !u.holdings?.some((h) => h.role === 'admin')
          )
          const sorted = [...nonAdmin].sort((a, b) => a.email.localeCompare(b.email))
          setUsers(sorted)
          if (sorted.length > 0) {
            setSelectedEmail((prev) => prev ?? sorted[0].email)
          }
        })
        .catch((err) => {
          console.error('Failed to fetch users:', err)
          alert('Не удалось загрузить список пользователей')
        })
    }
  }, [showUserSelect])

  const doSwitch = async (email: string, password: string) => {
    setLoading(true)
    try {
      const result = await loginUser({ email, password })
      localStorage.setItem(`dev_pw_${email}`, password)
      localStorage.setItem('access_token', result.access_token)
      setTokens(result.access_token)
      const user = await getCurrentUser()
      useAuthStore.getState().setUser(user)
      navigate('/', { replace: true })
    } catch (err) {
      console.error('Dev switch failed:', err)
      alert('Не удалось переключиться: ' + (err instanceof Error ? err.message : 'неизвестная ошибка'))
    } finally {
      setLoading(false)
    }
  }

  const handleSwitchToAdmin = () => {
    const saved = localStorage.getItem(`dev_pw_${ADMIN_EMAIL}`)
    if (saved) {
      doSwitch(ADMIN_EMAIL, saved)
    } else {
      setPassword('')
      setPasswordError('')
      setPasswordModal({ email: ADMIN_EMAIL, label: '👑 Админ' })
    }
  }

  const handleConfirmUserSwitch = async () => {
    if (!selectedEmail) return
    const saved = localStorage.getItem(`dev_pw_${selectedEmail}`)
    if (saved) {
      await doSwitch(selectedEmail, saved)
    } else {
      const user = users.find(u => u.email === selectedEmail)
      setPassword('')
      setPasswordError('')
      setPasswordModal({ email: selectedEmail, label: user?.email || selectedEmail })
    }
  }

  const handlePasswordSubmit = async () => {
    if (!passwordModal) return
    if (!password.trim()) {
      setPasswordError('Введите пароль')
      return
    }
    setPasswordError('')
    const { email } = passwordModal
    setPasswordModal(null)
    await doSwitch(email, password)
  }

  const handleForgetPassword = (email: string) => {
    localStorage.removeItem(`dev_pw_${email}`)
  }

  if (collapsed) {
    return (
      <div
        style={{
          position: 'fixed',
          bottom: 12,
          left: 12,
          zIndex: 9999,
        }}
      >
        <Button
          size="small"
          icon={<SwapOutlined />}
          onClick={() => setCollapsed(false)}
          title="Показать переключатель пользователей"
        />
      </div>
    )
  }

  return (
    <>
      <div
        style={{
          position: 'fixed',
          bottom: 12,
          left: 12,
          zIndex: 9999,
          background: '#fff',
          border: '1px solid #d9d9d9',
          borderRadius: 8,
          padding: '8px 12px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          maxWidth: 320,
        }}
      >
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text strong style={{ fontSize: 12, color: '#faad14' }}>
              🛠 DEV: Быстрое переключение
            </Text>
            <Button size="small" type="text" onClick={() => setCollapsed(true)} style={{ fontSize: 11 }}>
              ✕
            </Button>
          </div>

          <div style={{ display: 'flex', gap: 4 }}>
            <Button
              size="small"
              block
              loading={loading}
              onClick={handleSwitchToAdmin}
              style={{ textAlign: 'left', fontSize: 12 }}
            >
              👑 Админ
              {localStorage.getItem(`dev_pw_${ADMIN_EMAIL}`) ? ' 🔓' : ''}
            </Button>
            {localStorage.getItem(`dev_pw_${ADMIN_EMAIL}`) && (
              <Button
                size="small"
                type="text"
                danger
                onClick={() => handleForgetPassword(ADMIN_EMAIL)}
                title="Забыть пароль"
                style={{ fontSize: 11, padding: '0 4px' }}
              >
                ✕
              </Button>
            )}
          </div>

          {!showUserSelect ? (
            <Button
              size="small"
              block
              onClick={() => setShowUserSelect(true)}
              style={{ textAlign: 'left', fontSize: 12 }}
            >
              👤 Пользователь →
            </Button>
          ) : (
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Select
                size="small"
                style={{ width: '100%' }}
                value={selectedEmail}
                onChange={setSelectedEmail}
                options={users.map((u) => ({
                  label: u.email,
                  value: u.email,
                }))}
                placeholder="Выберите пользователя"
              />
              <Space>
                <Button size="small" type="primary" loading={loading} onClick={handleConfirmUserSwitch}>
                  Переключить
                </Button>
                <Button
                  size="small"
                  onClick={() => {
                    setShowUserSelect(false)
                    setSelectedEmail(null)
                  }}
                >
                  Отмена
                </Button>
              </Space>
            </Space>
          )}
        </Space>
      </div>

      <Modal
        title={`Пароль для ${passwordModal?.label || ''}`}
        open={!!passwordModal}
        onOk={handlePasswordSubmit}
        onCancel={() => setPasswordModal(null)}
        okText="Войти"
        cancelText="Отмена"
        confirmLoading={loading}
      >
        <Input.Password
          prefix={<LockOutlined />}
          placeholder="Введите пароль"
          value={password}
          onChange={(e) => { setPassword(e.target.value); setPasswordError('') }}
          onPressEnter={handlePasswordSubmit}
          autoFocus
          status={passwordError ? 'error' : undefined}
        />
        {passwordError && (
          <Text type="danger" style={{ fontSize: 12, marginTop: 4, display: 'block' }}>
            {passwordError}
          </Text>
        )}
      </Modal>
    </>
  )
}
