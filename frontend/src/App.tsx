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
import ProtectedRoute from './components/ProtectedRoute'
import HoldingRequired from './components/HoldingRequired'
import AppLayout from './components/AppLayout'

// Pages
import RegisterPage from './pages/RegisterPage'
import VerifyRegistrationPage from './pages/VerifyRegistrationPage'
import LoginPage from './pages/LoginPage'
import VerifyLoginPage from './pages/VerifyLoginPage'
import ProfilePage from './pages/ProfilePage'
import AdminHoldingsPage from './pages/AdminHoldingsPage'
import DashboardPage from './pages/DashboardPage'
import NotFoundPage from './pages/NotFoundPage'
import DocumentsListPage from './pages/DocumentsListPage'
import DocumentUploadPage from './pages/DocumentUploadPage'
import DocumentDetailPage from './pages/DocumentDetailPage'
import GeneratorPage from './pages/GeneratorPage'
import OrdersListPage from './pages/OrdersListPage'
import OrderUploadPage from './pages/OrderUploadPage'
import OrderDetailPage from './pages/OrderDetailPage'
import LegislationSearchPage from './pages/LegislationSearchPage'
import LegislationSourcesPage from './pages/LegislationSourcesPage'
import HoldingProfilePage from './pages/HoldingProfilePage'

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
        <Routes>
          {/* Public routes */}
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/verify-registration" element={<VerifyRegistrationPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/verify-login" element={<VerifyLoginPage />} />

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
              path="/admin/holdings"
              element={
                <HoldingRequired>
                  <AdminHoldingsPage />
                </HoldingRequired>
              }
            />
            <Route
              path="/"
              element={
                <HoldingRequired>
                  <DashboardPage />
                </HoldingRequired>
              }
            />
            <Route
              path="/documents"
              element={
                <HoldingRequired>
                  <DocumentsListPage />
                </HoldingRequired>
              }
            />
            <Route
              path="/documents/upload"
              element={
                <HoldingRequired>
                  <DocumentUploadPage />
                </HoldingRequired>
              }
            />
            <Route
              path="/documents/:id"
              element={
                <HoldingRequired>
                  <DocumentDetailPage />
                </HoldingRequired>
              }
            />
            <Route
              path="/generator"
              element={
                <HoldingRequired>
                  <GeneratorPage />
                </HoldingRequired>
              }
            />
            <Route
              path="/orders"
              element={
                <HoldingRequired>
                  <OrdersListPage />
                </HoldingRequired>
              }
            />
            <Route
              path="/orders/upload"
              element={
                <HoldingRequired>
                  <OrderUploadPage />
                </HoldingRequired>
              }
            />
            <Route
              path="/orders/:id"
              element={
                <HoldingRequired>
                  <OrderDetailPage />
                </HoldingRequired>
              }
            />
            <Route
              path="/legislation"
              element={
                <HoldingRequired>
                  <LegislationSearchPage />
                </HoldingRequired>
              }
            />
            <Route
              path="/legislation-sources"
              element={
                <HoldingRequired>
                  <LegislationSourcesPage />
                </HoldingRequired>
              }
            />
            <Route
              path="/holdings/:id/profile"
              element={
                <HoldingRequired>
                  <HoldingProfilePage />
                </HoldingRequired>
              }
            />
          </Route>

          {/* 404 */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  )
}
