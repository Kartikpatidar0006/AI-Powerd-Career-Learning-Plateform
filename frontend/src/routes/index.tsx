/**
 * Application router configuration.
 *
 * Defines all routes including public (login, signup) and
 * protected (dashboard) routes with the ProtectedRoute guard.
 */

import { createBrowserRouter, Navigate } from 'react-router-dom';
import LoginPage from '../pages/LoginPage';
import SignupPage from '../pages/SignupPage';
import DashboardPage from '../pages/DashboardPage';
import ProtectedRoute from '../components/ProtectedRoute';

const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/signup',
    element: <SignupPage />,
  },
  {
    // Protected routes — require authentication
    element: <ProtectedRoute />,
    children: [
      {
        path: '/dashboard',
        element: <DashboardPage />,
      },
    ],
  },
  {
    // Default redirect
    path: '*',
    element: <Navigate to="/login" replace />,
  },
]);

export default router;
