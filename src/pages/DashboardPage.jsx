import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Trophy,
  CheckCircle2,
  Video,
  Clock,
  ArrowRight,
  User,
  Compass,
  Map,
  Award,
  Bell,
  Star,
  Sparkles,
  Play,
} from 'lucide-react';
import PageHeader from '../components/PageHeader/PageHeader';
import Card from '../components/Card/Card';
import Button from '../components/Button/Button';
import Loader from '../components/Loader/Loader';
import EmptyState from '../components/EmptyState/EmptyState';
import ErrorState from '../components/ErrorState/ErrorState';
import dashboardService from '../services/dashboardService';
import notificationService from '../services/notificationService';
import { formatDateTime, formatDuration } from '../utils/formatters';

export const DashboardPage = () => {
  const [dashboardData, setDashboardData] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const data = await dashboardService.getStudentDashboard();
      setDashboardData(data);

      try {
        const notifRes = await notificationService.getMyNotifications({ limit: 5 });
        setNotifications(Array.isArray(notifRes) ? notifRes : notifRes.items || []);
      } catch {
        setNotifications([]);
      }
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        err.message ||
        'Failed to load student dashboard. Please check backend connection.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  if (loading) {
    return <Loader label="Loading student dashboard & analytics..." />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={fetchDashboardData} />;
  }

  if (!dashboardData) {
    return (
      <EmptyState
        title="Dashboard Data Unavailable"
        message="No dashboard information could be loaded for your account."
        actionLabel="Refresh Dashboard"
        onAction={fetchDashboardData}
      />
    );
  }

  const {
    user,
    profession,
    roadmap,
    current_task,
    latest_task_feedback,
    upcoming_interview,
    latest_interview_feedback,
    progress,
    unread_notification_count = 0,
  } = dashboardData;

  const isInterviewScheduled = upcoming_interview && upcoming_interview.status === 'Scheduled';

  return (
    <div>
      <PageHeader
        title={`Welcome back, ${user?.full_name || 'Learner'}!`}
        description="Here is your active career roadmap, task progress, and upcoming interview schedule."
      />

      {/* 1. Student Profile & Selected Career Overview Banner */}
      <Card style={{ marginBottom: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
            <div
              style={{
                width: '60px',
                height: '60px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
                fontSize: '1.5rem',
                fontWeight: 800,
              }}
            >
              {user?.full_name ? user.full_name.charAt(0).toUpperCase() : 'U'}
            </div>
            <div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-main)' }}>
                {user?.full_name}
              </h2>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginTop: '0.125rem' }}>
                {user?.email}
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
              <Compass size={20} style={{ color: 'var(--primary)' }} />
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', display: 'block' }}>Profession</span>
                <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-main)' }}>
                  {profession?.name || profession?.title || 'None Selected'}
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
              <Map size={20} style={{ color: 'var(--secondary)' }} />
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', display: 'block' }}>Active Roadmap</span>
                <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-main)' }}>
                  {roadmap?.title || 'None Active'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* 2. Platform Progress Metric Cards */}
      <div className="grid-4" style={{ marginBottom: '2rem' }}>
        <Card>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ padding: '0.75rem', borderRadius: 'var(--radius-md)', background: 'rgba(99, 102, 241, 0.15)', color: 'var(--primary)' }}>
              <Trophy size={24} />
            </div>
            <div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Overall Progress</p>
              <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)' }}>
                {progress?.overall_progress_percentage || 0}%
              </h3>
            </div>
          </div>
        </Card>

        <Card>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ padding: '0.75rem', borderRadius: 'var(--radius-md)', background: 'rgba(16, 185, 129, 0.15)', color: 'var(--accent-emerald)' }}>
              <CheckCircle2 size={24} />
            </div>
            <div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Tasks Completed</p>
              <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)' }}>
                {progress?.completed_tasks || 0}
              </h3>
            </div>
          </div>
        </Card>

        <Card>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ padding: '0.75rem', borderRadius: 'var(--radius-md)', background: 'rgba(168, 85, 247, 0.15)', color: 'var(--secondary)' }}>
              <Video size={24} />
            </div>
            <div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Interviews Done</p>
              <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)' }}>
                {progress?.completed_interviews || 0}
              </h3>
            </div>
          </div>
        </Card>

        <Card>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ padding: '0.75rem', borderRadius: 'var(--radius-md)', background: 'rgba(245, 158, 11, 0.15)', color: 'var(--accent-amber)' }}>
              <Clock size={24} />
            </div>
            <div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Skills in Progress</p>
              <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)' }}>
                {progress?.total_skills_in_progress || 0}
              </h3>
            </div>
          </div>
        </Card>
      </div>

      {/* 3. Main Desktop 2-Column Layout */}
      <div className="grid-2" style={{ marginBottom: '2rem' }}>
        
        {/* Left Column: Current Task & Upcoming Interview */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          
          {/* Current Task Card */}
          <Card title="Current Task Target" subtitle="Active learning task assigned in your career roadmap">
            {current_task ? (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.2rem 0.6rem', borderRadius: 'var(--radius-full)', background: 'var(--primary-light)', color: 'var(--primary)' }}>
                    {current_task.difficulty || 'Medium'}
                  </span>
                  <span style={{ fontSize: '0.8125rem', color: 'var(--text-dim)' }}>
                    Est: {formatDuration(current_task.estimated_minutes)}
                  </span>
                </div>
                <h4 style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
                  {current_task.title}
                </h4>
                <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1.5rem', lineHeight: 1.5 }}>
                  {current_task.description}
                </p>
                <Button variant="primary" icon={ArrowRight} onClick={() => navigate(`/tasks/${current_task.id}`)}>
                  Continue Task
                </Button>
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)' }}>No active task assigned. Explore roadmaps to begin!</p>
            )}
          </Card>

          {/* Upcoming Interview Card */}
          <Card title="Upcoming Mock Interview" subtitle="Scheduled technical & behavioral session">
            {upcoming_interview ? (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                    Date: {formatDateTime(upcoming_interview.scheduled_at)}
                  </span>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.2rem 0.6rem', borderRadius: 'var(--radius-full)', background: isInterviewScheduled ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255, 255, 255, 0.1)', color: isInterviewScheduled ? 'var(--accent-emerald)' : 'var(--text-muted)' }}>
                    {upcoming_interview.status}
                  </span>
                </div>
                <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
                  Duration: {upcoming_interview.duration_minutes || 10} minutes
                </p>
                <Button
                  variant="primary"
                  icon={Play}
                  disabled={!isInterviewScheduled}
                  onClick={() => navigate(`/interviews/${upcoming_interview.id}`)}
                >
                  Start Interview
                </Button>
              </div>
            ) : (
              <div>
                <p style={{ color: 'var(--text-muted)', marginBottom: '1.25rem' }}>
                  Complete a task evaluation with 70%+ score to automatically unlock an interview session.
                </p>
                <Button variant="secondary" onClick={() => navigate('/interviews')}>
                  View Interview History
                </Button>
              </div>
            )}
          </Card>

          {/* Overall Progress Bar Card */}
          <Card title="Overall Roadmap Progress">
            <div style={{ marginTop: '0.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Completion Rate</span>
                <span style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>{progress?.overall_progress_percentage || 0}%</span>
              </div>
              <div style={{ width: '100%', height: '10px', background: 'var(--bg-input)', borderRadius: 'var(--radius-full)', overflow: 'hidden' }}>
                <div
                  style={{
                    width: `${Math.min(100, progress?.overall_progress_percentage || 0)}%`,
                    height: '100%',
                    background: 'linear-gradient(90deg, var(--primary) 0%, var(--accent-emerald) 100%)',
                    transition: 'width 0.5s ease',
                  }}
                />
              </div>
            </div>
          </Card>

        </div>

        {/* Right Column: Feedbacks & Notification Widget */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

          {/* Latest Task Feedback Card */}
          <Card title="Latest Task Feedback" subtitle="Automated AI evaluation results">
            {latest_task_feedback ? (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
                  <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>Overall Score</span>
                  <span style={{ fontSize: '1.5rem', fontWeight: 800, color: latest_task_feedback.overall_score >= 70 ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
                    {latest_task_feedback.overall_score} / 100
                  </span>
                </div>
                {latest_task_feedback.strengths && (
                  <div style={{ marginBottom: '0.75rem' }}>
                    <p style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--accent-emerald)' }}>Strengths</p>
                    <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>{latest_task_feedback.strengths}</p>
                  </div>
                )}
                {latest_task_feedback.weaknesses && (
                  <div style={{ marginBottom: '0.75rem' }}>
                    <p style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--accent-rose)' }}>Weaknesses</p>
                    <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>{latest_task_feedback.weaknesses}</p>
                  </div>
                )}
                {latest_task_feedback.suggestions && (
                  <div>
                    <p style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--accent-amber)' }}>Suggestions</p>
                    <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>{latest_task_feedback.suggestions}</p>
                  </div>
                )}
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No task feedback recorded yet. Submit a task to receive AI evaluation.</p>
            )}
          </Card>

          {/* Latest Interview Feedback Card */}
          <Card title="Latest Interview Feedback" subtitle="Technical & behavioral performance metrics">
            {latest_interview_feedback ? (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
                  <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>Recommendation</span>
                  <span style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--accent-emerald)' }}>
                    {latest_interview_feedback.recommendation || 'Hire'}
                  </span>
                </div>
                <div className="grid-2" style={{ gap: '0.75rem', marginBottom: '1rem' }}>
                  <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-sm)' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Technical</span>
                    <p style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--primary)' }}>{latest_interview_feedback.technical_score}%</p>
                  </div>
                  <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-sm)' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Communication</span>
                    <p style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--secondary)' }}>{latest_interview_feedback.communication_score}%</p>
                  </div>
                  <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-sm)' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Confidence</span>
                    <p style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>{latest_interview_feedback.confidence_score}%</p>
                  </div>
                  <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-sm)' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Problem Solving</span>
                    <p style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--accent-emerald)' }}>{latest_interview_feedback.problem_solving_score}%</p>
                  </div>
                </div>
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No interview feedback recorded yet.</p>
            )}
          </Card>

          {/* Notifications Widget */}
          <Card
            title="Recent Notifications"
            headerAction={
              unread_notification_count > 0 ? (
                <span className="sidebar-badge">{unread_notification_count} unread</span>
              ) : null
            }
          >
            {notifications.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No recent notifications.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {notifications.slice(0, 5).map((notif) => (
                  <div key={notif.id} style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.5rem' }}>
                    <p style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-main)' }}>{notif.title}</p>
                    <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>{notif.message}</p>
                  </div>
                ))}
              </div>
            )}
          </Card>

        </div>

      </div>
    </div>
  );
};

export default DashboardPage;
