import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';

import ProtectedRoute from './ProtectedRoute';
import PublicRoute from './PublicRoute';
import StudentLayout from '../layouts/StudentLayout';

// Auth Pages
import LoginPage from '../pages/LoginPage';
import RegisterPage from '../pages/RegisterPage';

// Protected Student Pages
import DashboardPage from '../pages/DashboardPage';
import ProfessionSelectionPage from '../pages/ProfessionSelectionPage';
import RoadmapPage from '../pages/RoadmapPage';
import TaskListPage from '../pages/TaskListPage';
import TaskDetailsPage from '../pages/TaskDetailsPage';
import TaskSubmissionPage from '../pages/TaskSubmissionPage';
import TaskFeedbackPage from '../pages/TaskFeedbackPage';
import InterviewListPage from '../pages/InterviewListPage';
import InterviewPage from '../pages/InterviewPage';
import InterviewFeedbackPage from '../pages/InterviewFeedbackPage';
import ProgressPage from '../pages/ProgressPage';
import NotificationPage from '../pages/NotificationPage';
import ProfilePage from '../pages/ProfilePage';
import NotFoundPage from '../pages/NotFoundPage';

export const AppRoutes = () => {
  return (
    <Routes>
      {/* Root redirect */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      {/* Public Unauthenticated Routes */}
      <Route element={<PublicRoute />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      {/* Protected Student Layout Routes */}
      <Route element={<ProtectedRoute />}>
        <Route element={<StudentLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/professions" element={<ProfessionSelectionPage />} />
          <Route path="/roadmaps" element={<RoadmapPage />} />
          <Route path="/roadmaps/:roadmapId" element={<RoadmapPage />} />
          <Route path="/tasks" element={<TaskListPage />} />
          <Route path="/tasks/:taskId" element={<TaskDetailsPage />} />
          <Route path="/tasks/:taskId/submit" element={<TaskSubmissionPage />} />
          <Route path="/feedback/:taskId" element={<TaskFeedbackPage />} />
          <Route path="/interviews" element={<InterviewListPage />} />
          <Route path="/interviews/:interviewId" element={<InterviewPage />} />
          <Route path="/interviews/:interviewId/feedback" element={<InterviewFeedbackPage />} />
          <Route path="/progress" element={<ProgressPage />} />
          <Route path="/notifications" element={<NotificationPage />} />
          <Route path="/profile" element={<ProfilePage />} />
        </Route>
      </Route>

      {/* 404 Fallback Route */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
};

export default AppRoutes;
