import { useState } from 'react'
import { Form, Input, Button, Card, Typography, Alert, Space } from 'antd'
import { MailOutlined } from '@ant-design/icons'
import { Link, useNavigate } from 'react-router-dom'
import { registerUser } from '../api/auth'
import { getApiErrorMessage } from '../api/client'

const { Title, Text } = Typography

export default function RegisterPage() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successEmail, setSuccessEmail] = useState<string | null>(null)
  const navigate = useNavigate()

  const handleSubmit = async (values: { email: string }) => {
    setLoading(true)
    setError(null)
    setSuccessEmail(null)

    try {
      await registerUser({ email: values.email })
      setSuccessEmail(values.email)
      // Navigate to verify page after a short delay
      setTimeout(() => {
        navigate(`/verify-registration?email=${encodeURIComponent(values.email)}`)
      }, 1500)
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
            <Title level={2}>Регистрация</Title>
            <Text type="secondary">
              Введите email для создания аккаунта
            </Text>
          </div>

          {error && (
            <Alert
              message="Ошибка регистрации"
              description={error}
              type="error"
              showIcon
              closable
              onClose={() => setError(null)}
            />
          )}

          {successEmail && (
            <Alert
              message="Код отправлен!"
              description={`Проверочный код отправлен на ${successEmail}. Перенаправляем на страницу подтверждения...`}
              type="success"
              showIcon
            />
          )}

          <Form
            form={form}
            layout="vertical"
            onFinish={handleSubmit}
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
                disabled={loading}
              />
            </Form.Item>

            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                size="large"
              >
                Зарегистрироваться
              </Button>
            </Form.Item>
          </Form>

          <div style={{ textAlign: 'center' }}>
            <Text>
              Уже есть аккаунт?{' '}
              <Link to="/login">Войти</Link>
            </Text>
          </div>
        </Space>
      </Card>
    </div>
  )
}
