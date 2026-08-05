import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckSquare,
  Clock,
  ArrowRight,
  Sparkles,
  Bot,
  Lock,
  Unlock,
  Video,
  Mic,
  CheckCircle2,
  AlertCircle,
  Code2,
  TrendingUp,
  Award,
  Play,
  ShieldCheck,
} from 'lucide-react';
import PageHeader from '../components/PageHeader/PageHeader';
import Card from '../components/Card/Card';
import Button from '../components/Button/Button';
import Loader from '../components/Loader/Loader';
import EmptyState from '../components/EmptyState/EmptyState';
import taskService from '../services/taskService';
import dashboardService from '../services/dashboardService';

export const TaskListPage = () => {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [userProfile, setUserProfile] = useState(null);
  const [completedTaskIds, setCompletedTaskIds] = useState(['task-1']);
  const [completedInterviewIds, setCompletedInterviewIds] = useState([]);

  const navigate = useNavigate();

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [taskRes, dashRes] = await Promise.allSettled([
          taskService.getTasks(),
          dashboardService.getStudentDashboard(),
        ]);

        if (taskRes.status === 'fulfilled' && taskRes.value) {
          const raw = Array.isArray(taskRes.value) ? taskRes.value : taskRes.value.items || [];
          setTasks(raw);
        }

        if (dashRes.status === 'fulfilled' && dashRes.value) {
          setUserProfile(dashRes.value.profile || null);
          if (dashRes.value.progress?.completed_tasks > 0) {
            setCompletedTaskIds(['task-1']);
          }
        }
      } catch (err) {
        console.warn('Error loading task dashboard data:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const userLevel = userProfile?.experienceLevel || 'Intermediate';
  const userProfession = userProfile?.professionName || 'Machine Learning Engineer';

  // Dynamic daily task progression chain
  const dailyTaskChain = [
    {
      id: 'day-1',
      dayLabel: 'Day 1 Task',
      title: userProfession.includes('Machine')
        ? 'Build Automated ETL Feature Engineering Pipeline'
        : 'Build Interactive Kanban Task Board with State Hooks',
      difficulty: userLevel,
      estimatedMinutes: 45,
      description: userProfession.includes('Machine')
        ? 'Transform raw transactional datasets into normalized ML feature tables using Pandas and NumPy. Implement vectorized cleaning and outlier detection.'
        : 'Architect a responsive React Kanban board with drag-and-drop state persistence, local storage sync, and custom React hooks.',
      skills: userProfession.includes('Machine')
        ? ['Python 3.11', 'Pandas', 'Feature Scaling']
        : ['React 18', 'State Hooks', 'Custom Hooks'],
      status: completedTaskIds.includes('task-1') || completedTaskIds.includes('day-1') ? 'Completed' : 'Active',
      linkedInterview: {
        id: 'interview-1',
        title: userProfession.includes('Machine')
          ? 'Day 1 AI Technical Interview: Feature Store Architecture'
          : 'Day 1 AI Technical Interview: React Reconciliation & State Management',
        duration: '15 Mins',
        status: completedTaskIds.includes('task-1') || completedTaskIds.includes('day-1')
          ? completedInterviewIds.includes('interview-1')
            ? 'Completed'
            : 'Unlocked'
          : 'Locked',
      },
    },
    {
      id: 'day-2',
      dayLabel: 'Day 2 Task',
      title: userProfession.includes('Machine')
        ? 'Train XGBoost Classifier with MLflow Experiment Tracking'
        : 'Integrate Production REST API with Axios & Auth Interceptors',
      difficulty: userLevel,
      estimatedMinutes: 60,
      description: userProfession.includes('Machine')
        ? 'Train gradient boosting classification model, tune hyper-parameters using GridSearchCV, log metrics to MLflow, and export ONNX model artifact.'
        : 'Integrate external REST API services, write custom Axios request/response interceptors, manage JWT token refresh cycles, and handle optimistic UI updates.',
      skills: userProfession.includes('Machine')
        ? ['Scikit-Learn', 'XGBoost', 'MLflow']
        : ['Axios', 'REST APIs', 'JWT Auth'],
      status: completedInterviewIds.includes('interview-1') ? 'Active' : 'Locked',
      linkedInterview: {
        id: 'interview-2',
        title: userProfession.includes('Machine')
          ? 'Day 2 AI Technical Interview: Model Tuning & Overfitting Defenses'
          : 'Day 2 AI Technical Interview: Async JS & Interceptor Pipelines',
        duration: '20 Mins',
        status: 'Locked',
      },
    },
    {
      id: 'day-3',
      dayLabel: 'Day 3 Task',
      title: userProfession.includes('Machine')
        ? 'Deploy Async Model Inference API with FastAPI & Docker'
        : 'Optimize Vite Bundle Size & Core Web Vitals Performance',
      difficulty: 'Advanced',
      estimatedMinutes: 90,
      description: userProfession.includes('Machine')
        ? 'Build high-throughput async prediction endpoint using FastAPI, containerize with Docker multi-stage builds, and configure rate-limiting middleware.'
        : 'Implement code splitting, lazy loading image components, audit Lighthouse Core Web Vitals, and optimize production build bundles.',
      skills: userProfession.includes('Machine')
        ? ['FastAPI', 'Docker', 'MLOps']
        : ['Vite', 'Performance', 'Web Vitals'],
      status: 'Locked',
      linkedInterview: {
        id: 'interview-3',
        title: 'Day 3 AI Technical Interview: System Design & Production Deployment',
        duration: '25 Mins',
        status: 'Locked',
      },
    },
  ];

  if (loading) return <Loader label="AI Agent is assessing your experience level and assigning daily tasks..." />;

  return (
    <div>
      <PageHeader
        title="Adaptive AI Learning Tasks"
        description="Daily hands-on engineering assignments dynamically assigned to your skill level by the AI Learning Agent."
        breadcrumbs={[{ label: 'Tasks' }]}
      />

      {/* 1. ADAPTIVE AI AGENT LEVEL ASSESSMENT BANNER */}
      <Card className="dashboard-hero" style={{ padding: '1.75rem', marginBottom: '2rem' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1.25rem', flexWrap: 'wrap' }}>
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              boxShadow: '0 0 20px rgba(99, 102, 241, 0.5)',
              flexShrink: 0,
            }}
          >
            <Bot size={30} />
          </div>

          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem', flexWrap: 'wrap' }}>
              <span className="badge-pill badge-primary">
                <Sparkles size={12} /> ADAPTIVE AI AGENT
              </span>
              <span className="badge-pill badge-emerald">
                Level: {userLevel}
              </span>
              <span className="badge-pill badge-cyan">
                Track: {userProfession}
              </span>
            </div>

            <h3 style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-main)', fontFamily: 'var(--font-heading)' }}>
              1 Daily Task → Linked AI Mock Interview → Next Day Task Chain
            </h3>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '0.25rem', lineHeight: 1.5, maxWidth: '750px' }}>
              The AI Agent evaluates your daily progress. Completing today's engineering task unlocks your <strong>1-on-1 AI Technical Video Mock Interview</strong> directly below it. Completing the interview unlocks tomorrow's daily task!
            </p>
          </div>
        </div>
      </Card>

      {/* 2. DAILY PROGRESSION TIMELINE */}
      <div className="progression-chain">
        {dailyTaskChain.map((dayItem, idx) => {
          const isTaskCompleted = dayItem.status === 'Completed';
          const isTaskActive = dayItem.status === 'Active';
          const isTaskLocked = dayItem.status === 'Locked';

          return (
            <div key={dayItem.id} style={{ position: 'relative' }}>
              {/* Task Card */}
              <Card
                className={isTaskLocked ? 'locked-task-card' : ''}
                style={{
                  borderLeft: `4px solid ${
                    isTaskCompleted
                      ? 'var(--accent-emerald)'
                      : isTaskActive
                      ? 'var(--primary)'
                      : 'var(--border-subtle)'
                  }`,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '0.75rem' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                      <span className="badge-pill badge-primary">{dayItem.dayLabel}</span>
                      <span className="badge-pill badge-cyan">
                        <Clock size={12} /> Est. {dayItem.estimatedMinutes} Mins
                      </span>
                      <span className={`badge-pill ${isTaskCompleted ? 'badge-emerald' : isTaskActive ? 'badge-amber' : 'badge-primary'}`}>
                        {isTaskCompleted ? 'Completed ✓' : isTaskActive ? 'Active Today' : 'Locked 🔒'}
                      </span>
                    </div>

                    <h4 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-main)', fontFamily: 'var(--font-heading)' }}>
                      {dayItem.title}
                    </h4>
                  </div>

                  {isTaskLocked && (
                    <span className="lock-badge-overlay">
                      <Lock size={13} /> Complete Day {idx} Interview to Unlock
                    </span>
                  )}
                </div>

                <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: '1rem' }}>
                  {dayItem.description}
                </p>

                {/* Skill Pills */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                    {dayItem.skills.map((sk, sIdx) => (
                      <span key={sIdx} className="skill-tag">
                        <Code2 size={13} style={{ color: 'var(--primary)' }} /> {sk}
                      </span>
                    ))}
                  </div>

                  {!isTaskLocked && (
                    <Button
                      variant={isTaskCompleted ? 'secondary' : 'primary'}
                      icon={ArrowRight}
                      onClick={() => navigate('/tasks/1/submit')}
                    >
                      {isTaskCompleted ? 'Review Code Submission' : 'Start Task & Submit Code'}
                    </Button>
                  )}
                </div>
              </Card>

              {/* LINKED AI MOCK INTERVIEW UNLOCKED BOX */}
              {dayItem.linkedInterview && (
                <div
                  className="unlocked-interview-box"
                  style={{
                    opacity: dayItem.linkedInterview.status === 'Locked' ? 0.6 : 1,
                    filter: dayItem.linkedInterview.status === 'Locked' ? 'grayscale(0.4)' : 'none',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                    <div
                      style={{
                        width: '44px',
                        height: '44px',
                        borderRadius: '50%',
                        background: dayItem.linkedInterview.status === 'Unlocked'
                          ? 'linear-gradient(135deg, var(--accent-emerald) 0%, var(--primary) 100%)'
                          : 'var(--bg-input)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#ffffff',
                        boxShadow: dayItem.linkedInterview.status === 'Unlocked'
                          ? '0 0 15px rgba(16, 185, 129, 0.5)'
                          : 'none',
                      }}
                    >
                      {dayItem.linkedInterview.status === 'Unlocked' ? <Video size={22} /> : <Lock size={20} />}
                    </div>

                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
                        <span className="badge-pill badge-emerald" style={{ fontSize: '0.7rem' }}>
                          🎙️ AI MOCK INTERVIEW
                        </span>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          Duration: {dayItem.linkedInterview.duration}
                        </span>
                      </div>

                      <h5 style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--text-main)', margin: 0 }}>
                        {dayItem.linkedInterview.title}
                      </h5>
                      <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', margin: 0, marginTop: '0.2rem' }}>
                        {dayItem.linkedInterview.status === 'Unlocked'
                          ? '✅ Task 1 Completed! Your 1-on-1 AI Video Recruiter Interview is unlocked.'
                          : '🔒 Submit Day 1 Task code above to unlock your 1-on-1 AI Video Interview session.'}
                      </p>
                    </div>
                  </div>

                  {dayItem.linkedInterview.status === 'Unlocked' ? (
                    <Button
                      variant="primary"
                      icon={Video}
                      onClick={() => navigate('/interview')}
                    >
                      Launch 1-on-1 AI Video Interview
                    </Button>
                  ) : (
                    <span className="badge-pill badge-primary" style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }}>
                      <Lock size={12} style={{ marginRight: '0.25rem' }} /> Complete Task to Unlock
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default TaskListPage;

