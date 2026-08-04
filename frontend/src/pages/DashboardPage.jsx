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
  Flame,
  Code2,
  FolderGit2,
  RotateCcw,
  Check,
  Briefcase,
  Layers,
  Target,
  CheckSquare,
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
    return <Loader label="Loading student dashboard & real-time analytics..." />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={fetchDashboardData} />;
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
  } = dashboardData || {};

  // Pure database values — no fake fallbacks!
  const overallProgress = progress?.overall_progress_percentage || 0;
  const completedTasksCount = progress?.completed_tasks || 0;
  const completedInterviewsCount = progress?.completed_interviews || 0;
  const studyStreak = progress?.study_streak || 0;
  const jobReadinessScore = progress?.job_readiness_score || 0;
  const totalSkillsCompleted = progress?.total_skills_completed || 0;
  const totalSkillsInProgress = progress?.total_skills_in_progress || 0;

  const hasOnboarded = user?.onboarding_completed || Boolean(profession);
  const aiMatch = user?.ai_match_percentage || 0;

  const isInterviewScheduled = upcoming_interview && upcoming_interview.status === 'Scheduled';

  return (
    <div>
      <PageHeader
        title={`Welcome back, ${user?.full_name || 'Learner'}!`}
        description="Track your real database-backed learning progress, roadmap milestones, and task submissions."
      />

      {/* 1. SELECTED PROFESSION & ONBOARDING PROMPT BANNER */}
      {!hasOnboarded ? (
        <Card
          style={{
            marginBottom: '2rem',
            border: '2px solid var(--primary)',
            background: 'linear-gradient(135deg, rgba(15,23,42,0.95) 0%, rgba(99,102,241,0.2) 100%)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1.5rem' }}>
            <div>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.375rem',
                  padding: '0.25rem 0.75rem',
                  borderRadius: 'var(--radius-full)',
                  background: 'var(--primary-light)',
                  color: 'var(--primary)',
                  fontWeight: 800,
                  fontSize: '0.8125rem',
                  marginBottom: '0.5rem',
                }}
              >
                <Sparkles size={16} /> ONBOARDING ASSESSMENT REQUIRED
              </div>
              <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)' }}>
                Start Your AI Career Personalization Assessment
              </h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9375rem', marginTop: '0.25rem', maxWidth: '600px' }}>
                Complete the 9-step wizard and career assessment to calculate your AI career match, assign your active profession, and unlock your personalized roadmap.
              </p>
            </div>

            <Button variant="primary" size="lg" icon={ArrowRight} onClick={() => navigate('/onboarding')}>
              Start Onboarding Assessment
            </Button>
          </div>
        </Card>
      ) : (
        <Card
          style={{
            marginBottom: '2rem',
            border: '1px solid var(--primary-glow)',
            background: 'linear-gradient(135deg, rgba(15,23,42,0.9) 0%, rgba(99,102,241,0.1) 100%)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
              <div
                style={{
                  width: '64px',
                  height: '64px',
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fff',
                  fontSize: '1.75rem',
                  fontWeight: 800,
                  boxShadow: '0 0 20px var(--primary-glow)',
                }}
              >
                {user?.full_name ? user.full_name.charAt(0).toUpperCase() : 'U'}
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: 800,
                      padding: '0.15rem 0.5rem',
                      borderRadius: 'var(--radius-full)',
                      background: 'var(--primary-light)',
                      color: 'var(--primary)',
                    }}
                  >
                    SELECTED PROFESSION
                  </span>
                  {aiMatch > 0 && (
                    <span
                      style={{
                        fontSize: '0.75rem',
                        fontWeight: 800,
                        padding: '0.15rem 0.5rem',
                        borderRadius: 'var(--radius-full)',
                        background: 'rgba(16,185,129,0.15)',
                        color: 'var(--accent-emerald)',
                      }}
                    >
                      {aiMatch}% AI Match
                    </span>
                  )}
                </div>
                <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)', marginTop: '0.25rem' }}>
                  {profession?.name || profession?.title || 'Profession Assigned'}
                </h2>
                <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginTop: '0.125rem' }}>
                  {user?.email} • Daily Commitment: {user?.daily_study_time || '1 hour'}
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
              <Button variant="outline" icon={RotateCcw} onClick={() => navigate('/onboarding')}>
                Re-take Onboarding Assessment
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* 2. REAL DATABASE METRICS GRID */}
      <div className="grid-4" style={{ marginBottom: '2rem' }}>
        <Card>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ padding: '0.75rem', borderRadius: 'var(--radius-md)', background: 'rgba(99, 102, 241, 0.15)', color: 'var(--primary)' }}>
              <Trophy size={24} />
            </div>
            <div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Overall Progress</p>
              <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)' }}>
                {overallProgress}%
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
                {completedTasksCount}
              </h3>
            </div>
          </div>
        </Card>

        <Card>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ padding: '0.75rem', borderRadius: 'var(--radius-md)', background: 'rgba(245, 158, 11, 0.15)', color: 'var(--accent-amber)' }}>
              <Flame size={24} />
            </div>
            <div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Study Streak</p>
              <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)' }}>
                {studyStreak} Days 🔥
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
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Mock Interviews</p>
              <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)' }}>
                {completedInterviewsCount}
              </h3>
            </div>
          </div>
        </Card>
      </div>

      {/* 3. MAIN CONTENT GRID */}
      <div className="grid-2" style={{ marginBottom: '2rem' }}>
        
        {/* Left Column: Active Roadmap & Tasks */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          
          {/* ACTIVE ROADMAP WIDGET */}
          <Card title="Active Career Roadmap" subtitle={roadmap ? roadmap.title : 'Select a profession to activate roadmap'}>
            {roadmap ? (
              <div>
                <div style={{ marginBottom: '1.25rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem', marginBottom: '0.375rem' }}>
                    <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Roadmap Completion</span>
                    <span style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>{overallProgress}%</span>
                  </div>
                  <div style={{ width: '100%', height: '8px', background: 'var(--bg-input)', borderRadius: 'var(--radius-full)', overflow: 'hidden' }}>
                    <div style={{ width: `${overallProgress}%`, height: '100%', background: 'linear-gradient(90deg, var(--primary), var(--accent-emerald))', transition: 'width 0.3s ease' }} />
                  </div>
                </div>

                <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1.25rem', lineHeight: 1.5 }}>
                  {roadmap.description}
                </p>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.8125rem', color: 'var(--text-dim)' }}>
                    Est. Duration: {roadmap.estimated_months || 4} months
                  </span>
                  <Button variant="primary" icon={ArrowRight} onClick={() => navigate('/roadmaps')}>
                    Explore Full Roadmap
                  </Button>
                </div>
              </div>
            ) : (
              <EmptyState
                title="No Active Roadmap"
                message="Complete the onboarding assessment or browse career professions to activate your personalized roadmap."
                actionLabel="Explore Professions"
                onAction={() => navigate('/professions')}
              />
            )}
          </Card>

          {/* CURRENT TASK WIDGET */}
          <Card title="Current Active Task" subtitle="Assigned exercise in your roadmap">
            {current_task ? (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.2rem 0.6rem', borderRadius: 'var(--radius-full)', background: 'var(--primary-light)', color: 'var(--primary)' }}>
                    {current_task.difficulty || 'Medium'}
                  </span>
                  <span style={{ fontSize: '0.8125rem', color: 'var(--text-dim)' }}>
                    Est: {formatDuration(current_task.estimated_minutes || 60)}
                  </span>
                </div>
                <h4 style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
                  {current_task.title}
                </h4>
                <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1.25rem', lineHeight: 1.5 }}>
                  {current_task.description}
                </p>
                <Button variant="primary" icon={ArrowRight} onClick={() => navigate(`/tasks/${current_task.id}`)}>
                  Continue Task & Submit Code
                </Button>
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                No active tasks assigned yet. Select a career profession to begin your first module!
              </p>
            )}
          </Card>

          {/* LATEST TASK FEEDBACK WIDGET */}
          <Card title="Latest Task AI Evaluation" subtitle="Automated assessment feedback">
            {latest_task_feedback ? (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
                  <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>Evaluation Score</span>
                  <span style={{ fontSize: '1.5rem', fontWeight: 800, color: latest_task_feedback.overall_score >= 70 ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
                    {latest_task_feedback.overall_score} / 100
                  </span>
                </div>
                {latest_task_feedback.strengths && (
                  <div style={{ marginBottom: '0.75rem' }}>
                    <p style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--accent-emerald)' }}>Key Strengths</p>
                    <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>{latest_task_feedback.strengths}</p>
                  </div>
                )}
                {latest_task_feedback.suggestions && (
                  <div>
                    <p style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--accent-amber)' }}>AI Improvement Advice</p>
                    <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>{latest_task_feedback.suggestions}</p>
                  </div>
                )}
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                No task evaluation recorded. Submit a task with GitHub repository link to receive AI feedback.
              </p>
            )}
          </Card>
        </div>

        {/* Right Column: Skills, Job Readiness, Mock Interviews */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          
          {/* JOB READINESS SCORE WIDGET */}
          <Card title="Job Readiness Score" subtitle="Real-time career competency metric">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <div>
                <span style={{ fontSize: '2.25rem', fontWeight: 900, color: 'var(--accent-emerald)', fontFamily: 'var(--font-heading)' }}>
                  {jobReadinessScore}%
                </span>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Calculated from completed tasks & interviews</p>
              </div>
              <Target size={36} style={{ color: 'var(--accent-emerald)' }} />
            </div>
            <div style={{ width: '100%', height: '8px', background: 'var(--bg-input)', borderRadius: 'var(--radius-full)', overflow: 'hidden' }}>
              <div style={{ width: `${jobReadinessScore}%`, height: '100%', background: 'linear-gradient(90deg, var(--primary), var(--accent-emerald))' }} />
            </div>
          </Card>

          {/* SKILLS MASTERY PROFILE WIDGET */}
          <Card title="Skills Mastery Profile" subtitle="Real database tracked skill counts">
            <div className="grid-2" style={{ gap: '1rem', marginBottom: '1rem' }}>
              <div style={{ padding: '0.875rem', background: 'var(--bg-input)', borderRadius: 'var(--radius-md)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Completed Skills</span>
                <h4 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--accent-emerald)' }}>
                  {totalSkillsCompleted}
                </h4>
              </div>
              <div style={{ padding: '0.875rem', background: 'var(--bg-input)', borderRadius: 'var(--radius-md)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Skills In Progress</span>
                <h4 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--primary)' }}>
                  {totalSkillsInProgress}
                </h4>
              </div>
            </div>
          </Card>

          {/* UPCOMING MOCK INTERVIEWS WIDGET */}
          <Card title="Upcoming Mock Interview" subtitle="Scheduled technical AI session">
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
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1rem' }}>
                  Complete tasks with 70%+ score to unlock AI mock interview sessions.
                </p>
                <Button variant="secondary" onClick={() => navigate('/interviews')}>
                  View Mock Interviews
                </Button>
              </div>
            )}
          </Card>

          {/* RECENT NOTIFICATIONS WIDGET */}
          <Card title="Platform Activity Alerts" subtitle="Recent notifications">
            {notifications.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No recent notifications.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {notifications.slice(0, 4).map((notif) => (
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
