import { useState } from 'react'
import { Form, Input, Button, Card, Typography, Alert, Space } from 'antd'
import { MailOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { verifyLogin, loginUser } from '../api/auth'
import { getApiErrorMessage } from '../api/client'
import { useAuthStore } from '../store/authStore'

const { Title, Text } = Typography

export default function VerifyLoginPage() {
  const [form] = Form.useForm()
  const [searchParams] = useSearchParams()
  const emailFromUrl = searchParams.get('email') || ''
  const navigate = useNavigate()
  const { setTokens, setUser } = useAuthStore()

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (values: { email: string; code: string }) => {
    setLoading(true)
    setError(null)

    try {
      const tokens = await verifyLogin({
        email: values.email,
        code: values.code,
      })
      setTokens(tokens.access_token)
      setSuccess(true)

      // Redirect to profile (holding selection)
      setTimeout(() => {
        navigate('/profile')
      }, 1000)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const handleResendCode = async () => {
    const email = form.getFieldValue('email')
    if (!email) return

    setLoading(true)
    setError(null)
    try {
      await loginUser({ email })
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        background: '#f5f5f5',
      }}
    >
      <Card style={{ width: 420, boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div style={{ textAlign: 'center' }}>
            <Title level={2}>Подтверждение входа</Title>
            <Text type="secondary">
              Введите код из письма (проверьте консоль/лог сервера)
            </Text>
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

          {success && (
            <Alert
              message="Успешный вход!"
              description="Вы успешно вошли в систему. Перенаправляем..."
              type="success"
              showIcon
            />
          )}

          <Form
            form={form}
            layout="vertical"
            onFinish={handleSubmit}
            initialValues={{ email: emailFromUrl }}
            autoComplete="off"
          >
            <Form.Item
              name="email"
              label="Email"
              rules={[
                { required: true, message: 'Введите email' },
                { type: 'email', message: 'Некорректный email' },
              ]}
            >
              <Input
                prefix={<MailOutlined />}
                placeholder="user@example.com"
                size="large"
                disabled={loading || success}
              />
            </Form.Item>

            <Form.Item
              name="code"
              label="Код подтверждения"
              rules={[
                { required: true, message: 'Введите код' },
                { len: 6, message: 'Код должен содержать 6 цифр' },
                {
                  pattern: /^\d{6}$/,
                  message: 'Код должен состоять из 6 цифр',
                },
              ]}
            >
              <Input.OTP
                length={6}
                size="large"
                disabled={loading || success}
              />
            </Form.Item>

            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                size="large"
                disabled={success}
              >
                Войти
              </Button>
            </Form.Item>
          </Form>

          <Space direction="vertical" style={{ width: '100%', textAlign: 'center' }}>
            <Button type="link" onClick={handleResendCode} disabled={loading || success}>
              Отправить код повторно
            </Button>
            <Text>
              <Link to="/login">Назад ко входу</Link>
            </Text>
          </Space>
        </Space>
      </Card>
    </div>
  )
}
