import { Card, Typography, Space, Empty, Button } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { HomeOutlined, SettingOutlined, FileAddOutlined } from '@ant-design/icons'

const { Title, Text, Paragraph } = Typography

export default function DashboardPage() {
  const { user } = useAuthStore()
  const navigate = useNavigate()

  const companyName = user?.active_company
    ? `${user.active_company.legal_form} "${user.active_company.name}"`
    : ''

  return (
    <div>
      <Card>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <Title level={3}>Дашборд</Title>
            <Text type="secondary">
              Компания: <Text strong>{companyName}</Text>
            </Text>
          </div>

          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <Space direction="vertical" size="small">
                <Paragraph>
                  Добро пожаловать в СРП — Сервис управления регламентами.
                </Paragraph>
                <Paragraph type="secondary">
                  Здесь будет отображаться статистика документов, последние изменения
                  и быстрые действия. Пока что панель пуста — функционал появится в
                  следующих инкрементах.
                </Paragraph>
              </Space>
            }
          >
            <Space>
              <Button
                type="primary"
                icon={<FileAddOutlined />}
                disabled
              >
                Создать документ (скоро)
              </Button>
              <Button
                icon={<SettingOutlined />}
                onClick={() => navigate('/profile')}
              >
                Настройки профиля
              </Button>
            </Space>
          </Empty>
        </Space>
      </Card>
    </div>
  )
}
