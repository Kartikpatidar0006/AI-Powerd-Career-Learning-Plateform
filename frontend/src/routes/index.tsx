/**
 * Application router configuration.
 *
 * Defines all routes including:
 * - Public: /login, /signup
 * - Protected: /onboarding, /dashboard, /roadmap, /tasks, /history
 * - ProtectedRoute guard prevents unauthorized access
 * - Automatic routing checks profile lock status
 *
 * Week 3 additions: /roadmap, /tasks, /history routes
 */

import { createBrowserRouter, Navigate } from 'react-router-dom';
import LoginPage from '../pages/LoginPage';
import SignupPage from '../pages/SignupPage';
import DashboardPage from '../pages/DashboardPage';
import OnboardingPage from '../pages/OnboardingPage';
import RoadmapPage from '../pages/RoadmapPage';
import DailyTaskPage from '../pages/DailyTaskPage';
import TaskHistoryPage from '../pages/TaskHistoryPage';
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
        path: '/onboarding',
        element: <OnboardingPage />,
      },
      {
        path: '/dashboard',
        element: <DashboardPage />,
      },
      {
        path: '/roadmap',
        element: <RoadmapPage />,
      },
      {
        path: '/tasks',
        element: <DailyTaskPage />,
      },
      {
        path: '/history',
        element: <TaskHistoryPage />,
      },
      {
        path: '/',
        element: <Navigate to="/dashboard" replace />,
      },
    ],
  },
  {
    // Default redirect to login
    path: '*',
    element: <Navigate to="/login" replace />,
  },
]);

export default router;
