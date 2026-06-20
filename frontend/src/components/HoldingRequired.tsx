import { Navigate } from 'react-router-dom'
import { Spin } from 'antd'
import { useAuthStore } from '../store/authStore'

interface HoldingRequiredProps {
  children: React.ReactNode
}

/**
 * Redirects to /profile if the user has no active holding.
 * Must be nested inside ProtectedRoute.
 */
export default function HoldingRequired({ children }: HoldingRequiredProps) {
  const { user, isLoading } = useAuthStore()

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" tip="Загрузка..." />
      </div>
    )
  }

  if (!user?.active_holding) {
    return <Navigate to="/profile" replace />
  }

  return <>{children}</>
}
