import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Award, CheckCircle, AlertCircle, Video } from 'lucide-react';
import PageHeader from '../components/PageHeader/PageHeader';
import Card from '../components/Card/Card';
import Button from '../components/Button/Button';
import Loader from '../components/Loader/Loader';
import ErrorState from '../components/ErrorState/ErrorState';
import interviewService from '../services/interviewService';

export const TaskFeedbackPage = () => {
  const { taskId } = useParams();
  const [scheduling, setScheduling] = useState(false);
  const navigate = useNavigate();

  const handleScheduleInterview = async () => {
    try {
      setScheduling(true);
      const res = await interviewService.scheduleInterview(taskId);
      navigate(`/interviews/${res.id}`);
    } catch (err) {
      navigate('/interviews');
    } finally {
      setScheduling(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Task Evaluation Feedback"
        description="Detailed AI evaluation breakdown for your submitted solution."
        breadcrumbs={[{ label: 'Tasks', path: '/tasks' }, { label: 'Task Feedback' }]}
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', maxWidth: '900px' }}>
        {/* Score Card Banner */}
        <Card>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Overall Score</span>
              <h2 style={{ fontSize: '3rem', fontWeight: 800, color: 'var(--accent-emerald)', marginTop: '0.25rem' }}>85 / 100</h2>
              <p style={{ color: 'var(--accent-emerald)', fontWeight: 600, fontSize: '0.9375rem' }}>Passed (Minimum 70% required)</p>
            </div>
            <Button variant="primary" size="lg" icon={Video} isLoading={scheduling} onClick={handleScheduleInterview}>
              Start Mock Interview
            </Button>
          </div>
        </Card>

        {/* Detailed Breakdown */}
        <div className="grid-3">
          <Card title="Technical Score">
            <h3 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--primary)' }}>82%</h3>
          </Card>
          <Card title="Logic Score">
            <h3 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--secondary)' }}>88%</h3>
          </Card>
          <Card title="Code Quality">
            <h3 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--accent-cyan)' }}>80%</h3>
          </Card>
        </div>

        <Card title="Strengths & Highlights">
          <p style={{ color: 'var(--text-main)', lineHeight: 1.6 }}>
            Good problem solving logic, clean structure, and effective RESTful endpoint implementation.
          </p>
        </Card>

        <Card title="Areas for Improvement">
          <p style={{ color: 'var(--text-muted)', lineHeight: 1.6 }}>
            Could improve error handling documentation, docstrings, and unit test coverage.
          </p>
        </Card>
      </div>
    </div>
  );
};

export default TaskFeedbackPage;
