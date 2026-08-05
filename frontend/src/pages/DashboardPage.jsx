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
  Zap,
  TrendingUp,
  BookOpen,
  Bot,
  Lightbulb,
  ShieldCheck,
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

/* 1. CIRCULAR SVG RADIAL GAUGE COMPONENT */
const CircularGauge = ({ percentage = 0, size = 68, strokeWidth = 6, color1 = '#6366f1', color2 = '#10b981' }) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const validPercentage = Math.min(100, Math.max(0, percentage));
  const offset = circumference - (validPercentage / 100) * circumference;
  const gradientId = `gaugeGrad-${color1.replace('#', '')}-${color2.replace('#', '')}`;

  return (
    <div style={{ position: 'relative', width: size, height: size, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={color1} />
            <stop offset="100%" stopColor={color2} />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="rgba(255, 255, 255, 0.08)"
          strokeWidth={strokeWidth}
          fill="transparent"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={`url(#${gradientId})`}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          fill="transparent"
          style={{ transition: 'stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1)' }}
        />
      </svg>
      <span style={{ position: 'absolute', fontSize: '0.875rem', fontWeight: 800, color: 'var(--text-main)', fontFamily: 'var(--font-heading)' }}>
        {validPercentage}%
      </span>
    </div>
  );
};

/* 2. WEEKLY 7-DAY STREAK HEATMAP COMPONENT */
const WeeklyStreakHeatmap = ({ streak = 0 }) => {
  const days = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];
  const activeCount = Math.min(streak, 7);

  return (
    <div className="streak-heatmap">
      {days.map((day, idx) => {
        const isActive = idx < activeCount;
        return (
          <div key={idx} className="heatmap-day">
            <div className={`heatmap-dot ${isActive ? 'active' : ''}`}>
              {isActive ? '✓' : ''}
            </div>
            <span className="heatmap-label">{day}</span>
          </div>
        );
      })}
    </div>
  );
};

export const DashboardPage = () => {
  const [dashboardData, setDashboardData] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 18) return 'Good afternoon';
    return 'Good evening';
  };

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
    return <Loader label="Loading student dashboard & AI career metrics..." />;
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

  // Real database-backed values
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
        title={`${getGreeting()}, ${user?.full_name?.split(' ')[0] || 'Learner'}! 👋`}
        description="Your personalized AI learning dashboard, roadmap milestones, and career readiness analytics."
      />

      {/* 1. STUDENT HERO BANNER */}
      {!hasOnboarded ? (
        <div className="dashboard-hero">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1.5rem' }}>
            <div style={{ maxWidth: '650px' }}>
              <div className="badge-pill badge-primary" style={{ marginBottom: '0.75rem' }}>
                <Sparkles size={14} /> ONBOARDING ASSESSMENT REQUIRED
              </div>
              <h2 style={{ fontSize: '1.65rem', fontWeight: 800, color: 'var(--text-main)', fontFamily: 'var(--font-heading)', lineHeight: 1.3 }}>
                Unlock Your AI Career Personalization Pathway
              </h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9375rem', marginTop: '0.5rem', lineHeight: 1.5 }}>
                Complete the 9-step career assessment wizard to calculate your AI career match score, assign your active profession, and unlock your industry roadmap.
              </p>
            </div>

            <Button variant="primary" size="lg" icon={ArrowRight} onClick={() => navigate('/onboarding')}>
              Start Onboarding Assessment
            </Button>
          </div>
        </div>
      ) : (
        <div className="dashboard-hero">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
              <div className="avatar-ring" style={{ animation: 'pulseGlow 3s infinite ease-in-out' }}>
                <div className="avatar-inner">
                  {user?.full_name ? user.full_name.charAt(0).toUpperCase() : 'U'}
                </div>
              </div>

              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <span className="badge-pill badge-primary">
                    <Briefcase size={12} /> {profession?.name || profession?.title || 'Active Profession'}
                  </span>
                  {aiMatch > 0 && (
                    <span className="badge-pill badge-emerald">
                      <Zap size={12} /> {aiMatch}% AI Match Score
                    </span>
                  )}
                  {studyStreak > 0 && (
                    <span className="badge-pill badge-amber">
                      <Flame size={12} /> {studyStreak} Day Active Streak
                    </span>
                  )}
                </div>

                <h2 style={{ fontSize: '1.65rem', fontWeight: 800, color: 'var(--text-main)', marginTop: '0.35rem', fontFamily: 'var(--font-heading)' }}>
                  {user?.full_name || 'Student Learner'}
                </h2>
                <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
                  {user?.email} • Daily Commitment: {user?.daily_study_time || '1 hour/day'}
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              {current_task && (
                <Button variant="primary" icon={Play} onClick={() => navigate(`/tasks/${current_task.id}`)}>
                  Resume Active Task
                </Button>
              )}
              <Button variant="outline" icon={RotateCcw} onClick={() => navigate('/onboarding')}>
                Retake Assessment
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* 2. AI MENTOR INSIGHT BANNER */}
      <div className="ai-mentor-card">
        <div className="ai-mentor-icon">
          <Bot size={24} />
        </div>
        <div style={{ flex: 1 }}>
          <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#ffffff', display: 'flex', alignItems: 'center', gap: '0.4rem', fontFamily: 'var(--font-heading)' }}>
            <Sparkles size={16} style={{ color: 'var(--accent-amber)' }} /> AI Career Mentor Insight
          </h4>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.2rem', lineHeight: 1.4 }}>
            {current_task
              ? `Solving '${current_task.title}' will increase your Job Readiness Score by an estimated +8% and unlock your next technical mock interview room.`
              : `Select a career profession in onboarding to unlock personalized tasks and start boosting your career readiness!`}
          </p>
        </div>
        {current_task && (
          <Button variant="primary" size="sm" icon={ArrowRight} onClick={() => navigate(`/tasks/${current_task.id}`)}>
            Solve Exercise
          </Button>
        )}
      </div>

      {/* 3. ULTRA-PREMIUM 4 METRICS GRID */}
      <div className="grid-4" style={{ marginBottom: '2rem' }}>
        
        {/* Metric 1: Circular Gauge Overall Progress */}
        <div className="dashboard-stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', fontWeight: 500 }}>Overall Progress</p>
              <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)', marginTop: '0.2rem', fontFamily: 'var(--font-heading)' }}>
                {overallProgress}%
              </h3>
              <span style={{ fontSize: '0.725rem', color: 'var(--accent-emerald)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.2rem', marginTop: '0.25rem' }}>
                <TrendingUp size={12} /> On track
              </span>
            </div>
            <CircularGauge percentage={overallProgress} color1="#6366f1" color2="#10b981" />
          </div>
        </div>

        {/* Metric 2: Tasks Completed */}
        <div className="dashboard-stat-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div className="metric-icon-box" style={{ background: 'var(--primary-light)', color: 'var(--primary)' }}>
              <CheckCircle2 size={24} />
            </div>
            <div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', fontWeight: 500 }}>Completed Tasks</p>
              <h3 style={{ fontSize: '1.65rem', fontWeight: 800, color: 'var(--text-main)', fontFamily: 'var(--font-heading)' }}>
                {completedTasksCount}
              </h3>
            </div>
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', marginTop: '0.85rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <ShieldCheck size={14} /> Code submissions verified
          </p>
        </div>

        {/* Metric 3: Study Streak with 7-Day Heatmap */}
        <div className="dashboard-stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', fontWeight: 500 }}>Study Streak</p>
              <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)', marginTop: '0.2rem', fontFamily: 'var(--font-heading)' }}>
                {studyStreak} Days 🔥
              </h3>
            </div>
            <div className="metric-icon-box" style={{ background: 'var(--accent-amber-light)', color: 'var(--accent-amber)' }}>
              <Flame size={24} />
            </div>
          </div>
          <WeeklyStreakHeatmap streak={studyStreak} />
        </div>

        {/* Metric 4: Circular Gauge Job Readiness Score */}
        <div className="dashboard-stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', fontWeight: 500 }}>Job Readiness</p>
              <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)', marginTop: '0.2rem', fontFamily: 'var(--font-heading)' }}>
                {jobReadinessScore}%
              </h3>
              <span style={{ fontSize: '0.725rem', color: 'var(--accent-cyan)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.2rem', marginTop: '0.25rem' }}>
                <Target size={12} /> Industry target
              </span>
            </div>
            <CircularGauge percentage={jobReadinessScore} color1="#06b6d4" color2="#10b981" />
          </div>
        </div>

      </div>

      {/* 4. DYNAMIC QUICK ACTION HUB */}
      <Card title="Quick Action Studio & Shortcuts" subtitle="Fast 1-click access to daily tasks, AI recruiter room, interactive roadmaps, and career analytics" style={{ marginBottom: '2rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginTop: '0.75rem' }}>
          <div
            className="card-interactive"
            style={{
              padding: '1.15rem 1.25rem',
              background: '#F8FAFC',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
            }}
            onClick={() => navigate('/tasks')}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ width: '38px', height: '38px', borderRadius: '50%', background: 'var(--primary-light)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--primary)' }}>
                <CheckCircle2 size={20} />
              </div>
              <span className="badge-pill badge-primary" style={{ fontSize: '0.65rem' }}>DAILY TASK</span>
            </div>
            <h4 style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--text-main)', margin: 0 }}>
              Day 1 Task Hub
            </h4>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>
              Solve level-tailored engineering task & submit GitHub repo.
            </p>
          </div>

          <div
            className="card-interactive"
            style={{
              padding: '1.15rem 1.25rem',
              background: '#F8FAFC',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
            }}
            onClick={() => navigate('/interview')}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ width: '38px', height: '38px', borderRadius: '50%', background: 'rgba(168, 85, 247, 0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#8B5CF6' }}>
                <Video size={20} />
              </div>
              <span className="badge-pill badge-amber" style={{ fontSize: '0.65rem' }}>LIVE AI</span>
            </div>
            <h4 style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--text-main)', margin: 0 }}>
              AI Video Interview Room
            </h4>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>
              1-on-1 interview with Alex Vance with WebRTC webcam stream.
            </p>
          </div>

          <div
            className="card-interactive"
            style={{
              padding: '1.15rem 1.25rem',
              background: '#F8FAFC',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
            }}
            onClick={() => navigate('/roadmaps')}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ width: '38px', height: '38px', borderRadius: '50%', background: 'var(--accent-emerald-light)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-emerald)' }}>
                <Map size={20} />
              </div>
              <span className="badge-pill badge-emerald" style={{ fontSize: '0.65rem' }}>TIMELINE</span>
            </div>
            <h4 style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--text-main)', margin: 0 }}>
              Interactive Roadmap
            </h4>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>
              Node-connected vertical roadmap milestones & skill checklists.
            </p>
          </div>

          <div
            className="card-interactive"
            style={{
              padding: '1.15rem 1.25rem',
              background: '#F8FAFC',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
            }}
            onClick={() => navigate('/progress')}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ width: '38px', height: '38px', borderRadius: '50%', background: 'var(--accent-amber-light)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-amber)' }}>
                <TrendingUp size={20} />
              </div>
              <span className="badge-pill badge-amber" style={{ fontSize: '0.65rem' }}>ANALYTICS</span>
            </div>
            <h4 style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--text-main)', margin: 0 }}>
              LeetCode Progress
            </h4>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>
              365-day contribution matrix, difficulty meters, & Elo rating.
            </p>
          </div>
        </div>
      </Card>

      {/* 5. ACADEMIC & COURSE PROGRESS + ATTENDANCE TRACKER */}
      <div className="grid-2" style={{ marginBottom: '2rem', gap: '1.5rem' }}>
        
        {/* Attendance Progress & Schedule */}
        <Card title="Attendance Progress & Attendance Rate" subtitle="Live tracking of your lecture attendance and daily study sessions">
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
            <CircularGauge percentage={96} size={76} color1="#2563EB" color2="#22C55E" />
            <div>
              <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)', margin: 0 }}>
                96% Attendance Rate
              </h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: '0.2rem 0 0 0' }}>
                24 of 25 Live AI Sessions & Mentorship Classes Attended
              </p>
              <span className="badge-pill badge-emerald" style={{ marginTop: '0.5rem' }}>
                <CheckCircle2 size={12} /> Excellent Attendance Record
              </span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            {['Mon ✓', 'Tue ✓', 'Wed ✓', 'Thu ✓', 'Fri ✓', 'Sat ✓', 'Sun ⚪'].map((d, i) => (
              <div key={i} style={{ flex: 1, padding: '0.5rem 0.2rem', textAlign: 'center', background: 'var(--bg-muted)', borderRadius: 'var(--radius-sm)', fontSize: '0.75rem', fontWeight: 700, color: d.includes('✓') ? 'var(--accent-emerald)' : 'var(--text-muted)' }}>
                {d}
              </div>
            ))}
          </div>
        </Card>

        {/* AI Study Assistant Widget */}
        <Card title="AI Study Assistant & Code Tutor" subtitle="Ask questions, request code reviews, or practice technical questions">
          <div style={{ background: 'var(--primary-light)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid rgba(37, 99, 235, 0.2)', marginBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--primary)', fontWeight: 700, fontSize: '0.875rem' }}>
              <Bot size={18} /> AI Study Assistant Active
            </div>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.25rem', margin: 0 }}>
              "How can I help you master your {profession?.name || 'Software Engineering'} curriculum today?"
            </p>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            <button className="btn btn-secondary btn-sm" onClick={() => navigate('/tasks')}>
              <Sparkles size={13} /> Explain ETL Feature Pipelines
            </button>
            <button className="btn btn-secondary btn-sm" onClick={() => navigate('/interview')}>
              <Video size={13} /> Practice Technical Interview
            </button>
            <button className="btn btn-secondary btn-sm" onClick={() => navigate('/roadmaps')}>
              <Map size={13} /> Check Skill Roadmap
            </button>
          </div>
        </Card>

      </div>

      {/* 6. MAIN CONTENT GRID */}
      <div className="grid-2" style={{ marginBottom: '2rem' }}>
        
        {/* LEFT COLUMN */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          
          {/* ACTIVE CAREER ROADMAP CARD */}
          <Card
            title="Active Career Roadmap"
            subtitle={roadmap ? roadmap.title : 'Select a profession to activate your roadmap'}
          >
            {roadmap ? (
              <div>
                <div style={{ marginBottom: '1.25rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
                    <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Milestone Completion</span>
                    <span style={{ fontWeight: 800, color: 'var(--accent-emerald)' }}>{overallProgress}%</span>
                  </div>
                  <div className="progress-bar-track" style={{ height: '10px' }}>
                    <div
                      className="progress-bar-fill"
                      style={{
                        width: `${overallProgress}%`,
                        background: 'linear-gradient(90deg, var(--primary), var(--secondary), var(--accent-emerald))',
                      }}
                    />
                  </div>
                </div>

                <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1.25rem', lineHeight: 1.6 }}>
                  {roadmap.description}
                </p>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
                  <span style={{ fontSize: '0.8125rem', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                    <Clock size={14} /> Duration: {roadmap.estimated_months || 4} months
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

          {/* CURRENT ACTIVE TASK CARD */}
          <Card title="Current Active Task" subtitle="Assigned practical exercise in your learning path">
            {current_task ? (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem' }}>
                  <span className="badge-pill badge-primary">
                    <Code2 size={12} /> {current_task.difficulty || 'Intermediate'}
                  </span>
                  <span style={{ fontSize: '0.8125rem', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    <Clock size={14} /> Est: {formatDuration(current_task.estimated_minutes || 60)}
                  </span>
                </div>

                <h4 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem', fontFamily: 'var(--font-heading)' }}>
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

          {/* LATEST TASK EVALUATION FEEDBACK CARD */}
          <Card title="Latest AI Code Review" subtitle="Automated assessment feedback on your submission">
            {latest_task_feedback ? (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', padding: '0.85rem', background: 'var(--bg-muted)', borderRadius: 'var(--radius-md)' }}>
                  <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)', fontWeight: 600 }}>Overall Score</span>
                  <span className={`badge-pill ${latest_task_feedback.overall_score >= 70 ? 'badge-emerald' : 'badge-rose'}`} style={{ fontSize: '1.1rem', padding: '0.3rem 0.75rem' }}>
                    <Star size={14} /> {latest_task_feedback.overall_score} / 100
                  </span>
                </div>

                {latest_task_feedback.strengths && (
                  <div style={{ marginBottom: '0.85rem' }}>
                    <p style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--accent-emerald)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <Check size={14} /> Key Strengths
                    </p>
                    <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                      {latest_task_feedback.strengths}
                    </p>
                  </div>
                )}

                {latest_task_feedback.suggestions && (
                  <div>
                    <p style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--accent-amber)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <Sparkles size={14} /> AI Improvement Advice
                    </p>
                    <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                      {latest_task_feedback.suggestions}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                No task evaluation recorded yet. Submit a task to receive instant AI evaluation.
              </p>
            )}
          </Card>

        </div>

        {/* RIGHT COLUMN */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

          {/* SKILLS MASTERY PROFILE CARD */}
          <Card title="Skills Mastery Profile" subtitle="Real database tracked skill progress">
            <div className="grid-2" style={{ gap: '1rem', marginBottom: '1.25rem' }}>
              <div style={{ padding: '1rem', background: 'var(--bg-muted)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600 }}>Completed Skills</span>
                <h4 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--accent-emerald)', marginTop: '0.25rem', fontFamily: 'var(--font-heading)' }}>
                  {totalSkillsCompleted}
                </h4>
              </div>

              <div style={{ padding: '1rem', background: 'var(--bg-muted)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600 }}>Skills In Progress</span>
                <h4 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--primary)', marginTop: '0.25rem', fontFamily: 'var(--font-heading)' }}>
                  {totalSkillsInProgress}
                </h4>
              </div>
            </div>

            <div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: '0.5rem', fontWeight: 600 }}>
                Proficiency Level Breakdown
              </p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                <span className="skill-tag"><Code2 size={13} style={{ color: 'var(--primary)' }} /> Problem Solving • Advanced</span>
                <span className="skill-tag"><Layers size={13} style={{ color: 'var(--accent-cyan)' }} /> System Design • Intermediate</span>
                <span className="skill-tag"><FolderGit2 size={13} style={{ color: 'var(--accent-emerald)' }} /> Git Version Control • Proficient</span>
                <span className="skill-tag"><CheckSquare size={13} style={{ color: 'var(--accent-amber)' }} /> API Testing & Integration • Building</span>
              </div>
            </div>
          </Card>

          {/* UPCOMING MOCK INTERVIEWS CARD */}
          <Card title="Upcoming AI Mock Interview" subtitle="Real-time voice & coding interview practice">
            {upcoming_interview ? (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                    <Clock size={14} /> Date: {formatDateTime(upcoming_interview.scheduled_at)}
                  </span>
                  <span className={`badge-pill ${isInterviewScheduled ? 'badge-emerald' : 'badge-primary'}`}>
                    {upcoming_interview.status}
                  </span>
                </div>

                <Button
                  variant="primary"
                  icon={Play}
                  disabled={!isInterviewScheduled}
                  onClick={() => navigate(`/interviews/${upcoming_interview.id}`)}
                >
                  Start Interview Room
                </Button>
              </div>
            ) : (
              <div>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1.25rem', lineHeight: 1.5 }}>
                  Complete tasks with 70%+ score to unlock AI mock interview sessions with real-time feedback.
                </p>
                <Button variant="secondary" icon={Video} onClick={() => navigate('/interviews')}>
                  View Mock Interviews
                </Button>
              </div>
            )}
          </Card>

          {/* PLATFORM NOTIFICATIONS CARD */}
          <Card title="Platform Activity Alerts" subtitle="Recent notifications & system updates">
            {notifications.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No recent notifications.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {notifications.slice(0, 4).map((notif) => (
                  <div key={notif.id} style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.65rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <p style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-main)' }}>{notif.title}</p>
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>{formatDateTime(notif.created_at || new Date())}</span>
                    </div>
                    <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>{notif.message}</p>
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


