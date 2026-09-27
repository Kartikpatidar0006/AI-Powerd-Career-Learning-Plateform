/**
 * ProtectedRoute — guards routes that require authentication.
 *
 * Redirects unauthenticated users to the login page.
 * Shows a loading spinner while auth state is being determined.
 */

import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-3 border-primary-400 border-t-transparent rounded-full animate-spin" />
          <p className="text-surface-200 text-sm tracking-wide">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
