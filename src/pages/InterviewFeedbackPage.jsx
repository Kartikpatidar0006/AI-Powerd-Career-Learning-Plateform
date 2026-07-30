import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Award, CheckCircle, TrendingUp } from 'lucide-react';
import PageHeader from '../components/PageHeader/PageHeader';
import Card from '../components/Card/Card';
import Button from '../components/Button/Button';

export const InterviewFeedbackPage = () => {
  const { interviewId } = useParams();
  const navigate = useNavigate();

  return (
    <div>
      <PageHeader
        title="Interview Performance Evaluation"
        description="Comprehensive score breakdown and hiring manager feedback report."
        breadcrumbs={[{ label: 'Interviews', path: '/interviews' }, { label: 'Interview Report' }]}
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', maxWidth: '900px' }}>
        <Card>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Hiring Manager Recommendation</span>
              <h2 style={{ fontSize: '2.5rem', fontWeight: 800, color: 'var(--accent-emerald)', marginTop: '0.25rem' }}>Strong Hire</h2>
              <p style={{ color: 'var(--text-muted)' }}>Overall Score: 86 / 100</p>
            </div>
            <Button variant="primary" icon={TrendingUp} onClick={() => navigate('/progress')}>
              View Career Progress
            </Button>
          </div>
        </Card>

        <div className="grid-4">
          <Card title="Technical">
            <h3 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--primary)' }}>84%</h3>
          </Card>
          <Card title="Communication">
            <h3 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--secondary)' }}>88%</h3>
          </Card>
          <Card title="Confidence">
            <h3 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--accent-cyan)' }}>85%</h3>
          </Card>
          <Card title="Problem Solving">
            <h3 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--accent-emerald)' }}>87%</h3>
          </Card>
        </div>

        <Card title="Observed Strengths">
          <p style={{ color: 'var(--text-main)', lineHeight: 1.6 }}>
            Clear technical explanations, structured problem-solving logic, and confident verbal/written delivery across all questions.
          </p>
        </Card>

        <Card title="Actionable Suggestions">
          <p style={{ color: 'var(--text-muted)', lineHeight: 1.6 }}>
            Practice detailing time and space complexity trade-offs explicitly and walk through edge case scenarios step-by-step.
          </p>
        </Card>
      </div>
    </div>
  );
};

export default InterviewFeedbackPage;
