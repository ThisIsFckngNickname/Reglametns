import { Layout, Button, Typography, Space, Tag } from 'antd'
import { LogoutOutlined, UserOutlined, HomeOutlined, FileTextOutlined, UploadOutlined, RobotOutlined, OrderedListOutlined, SearchOutlined, GlobalOutlined } from '@ant-design/icons'
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

  const holdingName = user?.active_holding
    ? `${user.active_holding.legal_form} "${user.active_holding.name}"`
    : null

  // Determine active nav item
  const isDocumentsActive = location.pathname.startsWith('/documents')
  const isGeneratorActive = location.pathname.startsWith('/generator')
  const isOrdersActive = location.pathname.startsWith('/orders')
  const isLegislationActive = location.pathname.startsWith('/legislation')
  const isSourcesActive = location.pathname.startsWith('/legislation-sources')

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
            Реестр документов
          </Button>
          <Button
            type="text"
            icon={<UploadOutlined />}
            onClick={() => navigate('/documents/upload')}
          >
            Загрузить
          </Button>
          <Button
            type={isOrdersActive ? 'primary' : 'text'}
            icon={<OrderedListOutlined />}
            onClick={() => navigate('/orders')}
          >
            Приказы
          </Button>
          <Button
            type={isGeneratorActive ? 'primary' : 'text'}
            icon={<RobotOutlined />}
            onClick={() => navigate('/generator')}
          >
            Генератор
          </Button>
          <Button
            type={isLegislationActive ? 'primary' : 'text'}
            icon={<SearchOutlined />}
            onClick={() => navigate('/legislation')}
          >
            Поиск законов
          </Button>
          <Button
            type={isSourcesActive ? 'primary' : 'text'}
            icon={<GlobalOutlined />}
            onClick={() => navigate('/legislation-sources')}
          >
            Источники
          </Button>
        </Space>
      </Space>

      {/* Right side: Holding info + User info */}
      <Space size="middle">
        {holdingName && (
          <Tag color="blue" style={{ fontSize: 13, padding: '2px 12px' }}>
            {holdingName}
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
