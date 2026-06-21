import { Navigate } from 'react-router-dom'
import { Spin } from 'antd'
import { useAuthStore } from '../store/authStore'

interface CompanyRequiredProps {
  children: React.ReactNode
}

/**
 * Redirects to /profile if the user has no active company.
 * Must be nested inside ProtectedRoute.
 */
export default function CompanyRequired({ children }: CompanyRequiredProps) {
  const { user, isLoading } = useAuthStore()

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" tip="Загрузка..." />
      </div>
    )
  }

  if (!user?.active_company) {
    return <Navigate to="/profile" replace />
  }

  return <>{children}</>
}
