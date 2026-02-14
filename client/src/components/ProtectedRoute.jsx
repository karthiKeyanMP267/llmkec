import { Navigate } from 'react-router-dom'

export default function ProtectedRoute({ session, allowRoles, children }) {
  if (!session) return <Navigate to="/login" replace />
  if (Array.isArray(allowRoles) && !allowRoles.includes(session.role)) return <Navigate to="/login" replace />
  return children
}
