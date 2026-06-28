import { Layout, Button, Typography, Space, Tag } from 'antd'
import { LogoutOutlined, UserOutlined, HomeOutlined, FileTextOutlined, RobotOutlined, SettingOutlined, BookOutlined } from '@ant-design/icons'
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
  const isTermsActive = location.pathname.startsWith('/terms')

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
          СРП
        </Button>

        <Space size="small">
          <Button
            type={isGeneratorActive ? 'primary' : 'text'}
            icon={<RobotOutlined />}
            onClick={() => navigate('/generator')}
          >
            Генератор
          </Button>
          <Button
            type={isTermsActive ? 'primary' : 'text'}
            icon={<BookOutlined />}
            onClick={() => navigate('/terms')}
          >
            Термины и сокращения
          </Button>
          <Button
            type={isDocumentsActive ? 'primary' : 'text'}
            icon={<FileTextOutlined />}
            onClick={() => navigate('/documents')}
          >
            Документы
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

        {user?.active_company && user?.companies && (
          (() => {
            const membership = user.companies.find(c => c.company_id === user.active_company?.id)
            const roleLabels: Record<string, { label: string; color: string }> = {
              admin: { label: 'Админ', color: 'red' },
              editor: { label: 'Редактор', color: 'blue' },
              member: { label: 'Редактор', color: 'blue' },
              viewer: { label: 'Просмотр', color: 'default' },
            }
            const roleInfo = membership ? roleLabels[membership.role] || { label: membership.role, color: 'default' } : null
            return roleInfo ? (
              <Tag color={roleInfo.color} style={{ fontSize: 12 }}>
                {roleInfo.label}
              </Tag>
            ) : null
          })()
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
