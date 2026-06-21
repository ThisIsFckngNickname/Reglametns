import { lazy, Suspense } from 'react'
import { Layout } from 'antd'
import { Outlet } from 'react-router-dom'
import Header from './Header'

const { Content } = Layout

const DevUserSwitcher = import.meta.env.VITE_DEV_TOOLS === 'true'
  ? lazy(() => import('./DevUserSwitcher'))
  : null

export default function AppLayout() {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header />
      <Content style={{ padding: '24px', maxWidth: 1200, width: '100%', margin: '0 auto' }}>
        <Outlet />
      </Content>
      {DevUserSwitcher && (
        <Suspense fallback={null}>
          <DevUserSwitcher />
        </Suspense>
      )}
    </Layout>
  )
}
