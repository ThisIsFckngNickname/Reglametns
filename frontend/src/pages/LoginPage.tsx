import { useState } from 'react'
import { Form, Input, Button, Card, Typography, Alert, Space } from 'antd'
import { MailOutlined } from '@ant-design/icons'
import { Link, useNavigate } from 'react-router-dom'
import { loginUser } from '../api/auth'
import { getApiErrorMessage } from '../api/client'

const { Title, Text } = Typography

export default function LoginPage() {
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
      await loginUser({ email: values.email })
      setSuccessEmail(values.email)
      setTimeout(() => {
        navigate(`/verify-login?email=${encodeURIComponent(values.email)}`)
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
            <Title level={2}>Вход</Title>
            <Text type="secondary">
              Введите email для получения кода входа
            </Text>
          </div>

          {error && (
            <Alert
              message="Ошибка входа"
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
              description={`Проверочный код отправлен на ${successEmail}. Перенаправляем...`}
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
                Получить код
              </Button>
            </Form.Item>
          </Form>

          <div style={{ textAlign: 'center' }}>
            <Text>
              Нет аккаунта?{' '}
              <Link to="/register">Зарегистрироваться</Link>
            </Text>
          </div>
        </Space>
      </Card>
    </div>
  )
}
