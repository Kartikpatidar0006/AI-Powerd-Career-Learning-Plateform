import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { LayoutDashboard, ArrowRight, CheckCircle2, Trophy, Clock, Video } from 'lucide-react';
import PageHeader from '../components/PageHeader/PageHeader';
import Card from '../components/Card/Card';
import Button from '../components/Button/Button';
import Loader from '../components/Loader/Loader';
import ErrorState from '../components/ErrorState/ErrorState';
import dashboardService from '../services/dashboardService';

export const DashboardPage = () => {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const fetchDashboard = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await dashboardService.getStudentDashboard();
      setDashboardData(data);
    } catch (err) {
      setError(err.message || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, []);

  if (loading) return <Loader label="Loading student dashboard..." />;
  if (error) return <ErrorState message={error} onRetry={fetchDashboard} />;

  const { profession, roadmap, current_task, upcoming_interview, progress } = dashboardData || {};

  return (
    <div>
      <PageHeader
        title="Student Dashboard"
        description="Welcome back! Track your career roadmap, complete assignments, and prepare for mock interviews."
      />

      {/* Progress Metric Banner */}
      <div className="grid-4" style={{ marginBottom: '2rem' }}>
        <Card>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ padding: '0.75rem', borderRadius: 'var(--radius-md)', background: 'rgba(99, 102, 241, 0.15)', color: 'var(--primary)' }}>
              <Trophy size={24} />
            </div>
            <div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Overall Progress</p>
              <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)' }}>{progress?.overall_progress_percentage || 0}%</h3>
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
              <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)' }}>{progress?.completed_tasks || 0}</h3>
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
              <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)' }}>{progress?.completed_interviews || 0}</h3>
            </div>
          </div>
        </Card>

        <Card>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ padding: '0.75rem', borderRadius: 'var(--radius-md)', background: 'rgba(245, 158, 11, 0.15)', color: 'var(--accent-amber)' }}>
              <Clock size={24} />
            </div>
            <div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Active Skills</p>
              <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)' }}>{progress?.total_skills_in_progress || 0}</h3>
            </div>
          </div>
        </Card>
      </div>

      {/* Main Focus Cards */}
      <div className="grid-2" style={{ marginBottom: '2rem' }}>
        <Card title="Current Target Task" subtitle="Active learning task assigned in your career roadmap">
          {current_task ? (
            <div>
              <h4 style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem' }}>{current_task.title}</h4>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1.5rem', lineHeight: 1.5 }}>{current_task.description}</p>
              <Button variant="primary" icon={ArrowRight} onClick={() => navigate(`/tasks/${current_task.id}`)}>
                Start Task
              </Button>
            </div>
          ) : (
            <p style={{ color: 'var(--text-muted)' }}>No active task assigned. Explore roadmaps to begin!</p>
          )}
        </Card>

        <Card title="Upcoming Mock Interview" subtitle="Scheduled technical & behavioral session">
          {upcoming_interview ? (
            <div>
              <h4 style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem' }}>Mock Interview Session</h4>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1.5rem' }}>Scheduled status: {upcoming_interview.status}</p>
              <Button variant="secondary" icon={Video} onClick={() => navigate(`/interviews/${upcoming_interview.id}`)}>
                View Interview Room
              </Button>
            </div>
          ) : (
            <div>
              <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem' }}>Complete a task evaluation with 70%+ score to unlock automated interview scheduling.</p>
              <Button variant="outline" onClick={() => navigate('/interviews')}>
                View Interview History
              </Button>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};

export default DashboardPage;
