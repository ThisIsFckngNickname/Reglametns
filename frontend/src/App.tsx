import { useEffect } from 'react'
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
} from 'react-router-dom'
import { ConfigProvider } from 'antd'
import ruRU from 'antd/locale/ru_RU'
import { useAuthStore } from './store/authStore'
import { getCurrentUser } from './api/auth'
import ErrorBoundary from './components/ErrorBoundary'
import ProtectedRoute from './components/ProtectedRoute'
import CompanyRequired from './components/CompanyRequired'
import AdminRoute from './components/AdminRoute'
import AppLayout from './components/AppLayout'

// Pages
import RegisterPage from './pages/RegisterPage'
import LoginPage from './pages/LoginPage'
import ProfilePage from './pages/ProfilePage'
import AdminCompaniesPage from './pages/AdminCompaniesPage'
import DashboardPage from './pages/DashboardPage'
import NotFoundPage from './pages/NotFoundPage'
import DocumentsListPage from './pages/DocumentsListPage'
import DocumentUploadPage from './pages/DocumentUploadPage'
import DocumentDetailPage from './pages/DocumentDetailPage'
import GeneratorPage from './pages/GeneratorPage'
import CompanyProfilePage from './pages/CompanyProfilePage'
import AdminUsersPage from './pages/AdminUsersPage'
import TermsPage from './pages/TermsPage'

export default function App() {
  const { initialize, isAuthenticated, setUser, logout, isLoading } =
    useAuthStore()

  // Initialize auth: try to refresh token via httpOnly cookie on mount
  useEffect(() => {
    initialize()
  }, [initialize])

  // Fetch user profile when authenticated (safety net)
  useEffect(() => {
    if (isAuthenticated) {
      getCurrentUser()
        .then((user) => setUser(user))
        .catch(() => {
          // If token is invalid, log out
          logout()
        })
    }
  }, [isAuthenticated, setUser, logout])

  // Show a loading screen while checking auth
  if (isLoading) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
          fontSize: 18,
          color: '#888',
        }}
      >
        Загрузка...
      </div>
    )
  }

  return (
    <ConfigProvider locale={ruRU}>
      <BrowserRouter>
        <ErrorBoundary title="Ошибка в приложении" description="Произошла критическая ошибка. Перезагрузите страницу или вернитесь позже.">
        <Routes>
          {/* Public routes */}
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/login" element={<LoginPage />} />

          {/* Protected routes */}
          <Route
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/profile" element={<ProfilePage />} />
            <Route
              path="/admin/companies"
              element={
                <AdminRoute>
                  <AdminCompaniesPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/users"
              element={
                <AdminRoute>
                  <AdminUsersPage />
                </AdminRoute>
              }
            />
            <Route
              path="/"
              element={
                <CompanyRequired>
                  <DashboardPage />
                </CompanyRequired>
              }
            />
            <Route
              path="/documents"
              element={
                <CompanyRequired>
                  <DocumentsListPage />
                </CompanyRequired>
              }
            />
            <Route
              path="/documents/upload"
              element={
                <CompanyRequired>
                  <DocumentUploadPage />
                </CompanyRequired>
              }
            />
            <Route
              path="/documents/:id"
              element={
                <CompanyRequired>
                  <ErrorBoundary title="Ошибка загрузки документа">
                    <DocumentDetailPage />
                  </ErrorBoundary>
                </CompanyRequired>
              }
            />
            <Route
              path="/generator"
              element={
                <CompanyRequired>
                  <GeneratorPage />
                </CompanyRequired>
              }
            />
            <Route
              path="/terms"
              element={
                <CompanyRequired>
                  <TermsPage />
                </CompanyRequired>
              }
            />
            <Route
              path="/companies/:id/profile"
              element={
                <CompanyRequired>
                  <CompanyProfilePage />
                </CompanyRequired>
              }
            />
          </Route>

          {/* 404 */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
        </ErrorBoundary>
      </BrowserRouter>
    </ConfigProvider>
  )
}
