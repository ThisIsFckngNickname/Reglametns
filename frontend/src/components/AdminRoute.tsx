import { Navigate } from 'react-router-dom'
import { Spin } from 'antd'
import { useAuthStore } from '../store/authStore'

interface AdminRouteProps {
  children: React.ReactNode
}

/**
 * Проверяет, что пользователь аутентифицирован и является админом холдинга.
 */
export default function AdminRoute({ children }: AdminRouteProps) {
  const { user, isLoading } = useAuthStore()

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" tip="Загрузка..." />
      </div>
    )
  }

  // Проверяем роль admin через companies пользователя
  // Если пользователь не залогинен — редирект на логин
  if (!user) {
    return <Navigate to="/login" replace />
  }

  const isAdmin = user.companies?.some((h) => h.role === 'admin')

  if (!isAdmin) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
