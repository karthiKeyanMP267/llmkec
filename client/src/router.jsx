import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import AdminIngestionPage from './pages/AdminIngestionPage'
import ChatPage from './pages/ChatPage'
import LoginPage from './pages/LoginPage'
import ProtectedRoute from './components/ProtectedRoute'
import { useAuth } from './hooks/useAuth'

const defaultRouteForRole = (role) => (role === 'ADMIN' ? '/admin' : '/chat')

function RouterBody() {
  const navigate = useNavigate()
  const location = useLocation()
  const { session, status, error, loading, setError, login, logout } = useAuth()

  const handleLogin = async (email, password) => {
    const result = await login(email, password)
    if (result.ok && result.session) {
      navigate(defaultRouteForRole(result.session.role), { replace: true })
    }
  }

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const currentPath = location.pathname
  const shouldRedirectHome = session && (currentPath === '/' || currentPath === '/login' || currentPath === '/#')

  if (shouldRedirectHome) {
    return <Navigate to={defaultRouteForRole(session.role)} replace />
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage onLogin={handleLogin} status={status} error={error} loading={loading} clearError={() => setError('')} />} />
      <Route
        path="/admin"
        element={(
          <ProtectedRoute session={session} allowRoles={['ADMIN']}>
            <AdminIngestionPage session={session} onLogout={handleLogout} />
          </ProtectedRoute>
        )}
      />
      <Route
        path="/chat"
        element={(
          <ProtectedRoute session={session} allowRoles={['ADMIN', 'STUDENT', 'FACULTY']}>
            <ChatPage session={session} onLogout={handleLogout} />
          </ProtectedRoute>
        )}
      />
      <Route path="/" element={<Navigate to={session ? defaultRouteForRole(session.role) : '/login'} replace />} />
      <Route path="*" element={<Navigate to={session ? defaultRouteForRole(session.role) : '/login'} replace />} />
    </Routes>
  )
}

export default function AppRouter() {
  return <RouterBody />
}
