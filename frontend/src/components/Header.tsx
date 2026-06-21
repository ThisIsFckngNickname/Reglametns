import { Layout, Button, Typography, Space, Tag } from 'antd'
import { LogoutOutlined, UserOutlined, HomeOutlined, FileTextOutlined, RobotOutlined, SettingOutlined } from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'

const { Text } = Typography

export default function Header() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const companyName = user?.active_company
    ? `${user.active_company.legal_form} "${user.active_company.name}"`
    : null

  // Determine active nav item
  const isDocumentsActive = location.pathname.startsWith('/documents')
  const isGeneratorActive = location.pathname.startsWith('/generator')

  return (
    <Layout.Header
      style={{
        background: '#fff',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid #f0f0f0',
        height: 64,
      }}
    >
      {/* Left side: Logo + Navigation */}
      <Space size="large">
        <Button
          type="text"
          icon={<HomeOutlined />}
          onClick={() => navigate('/')}
          style={{ fontSize: 18, fontWeight: 600 }}
        >
          SRP
        </Button>

        <Space size="small">
          <Button
            type={isDocumentsActive ? 'primary' : 'text'}
            icon={<FileTextOutlined />}
            onClick={() => navigate('/documents')}
          >
            Документы
          </Button>
          <Button
            type={isGeneratorActive ? 'primary' : 'text'}
            icon={<RobotOutlined />}
            onClick={() => navigate('/generator')}
          >
            Генератор
          </Button>
          {user?.companies?.some(h => h.role === 'admin') && (
            <Button
              type={(location.pathname.startsWith('/admin')) ? 'primary' : 'text'}
              icon={<SettingOutlined />}
              onClick={() => navigate('/admin/companies')}
            >
              Админка
            </Button>
          )}
        </Space>
      </Space>

      {/* Right side: Company info + User info */}
      <Space size="middle">
        {companyName && (
          <Tag color="blue" style={{ fontSize: 13, padding: '2px 12px' }}>
            {companyName}
          </Tag>
        )}

        {user && (
          <Text type="secondary">
            <UserOutlined style={{ marginRight: 4 }} />
            {user.email}
          </Text>
        )}

        <Button
          type="text"
          icon={<LogoutOutlined />}
          onClick={handleLogout}
          danger
        >
          Выйти
        </Button>
      </Space>
    </Layout.Header>
  )
}
