import React, { useState, useEffect } from 'react';
import { TrendingUp, Award, CheckCircle, Clock } from 'lucide-react';
import PageHeader from '../components/PageHeader/PageHeader';
import Card from '../components/Card/Card';
import Loader from '../components/Loader/Loader';
import progressService from '../services/progressService';

export const ProgressPage = () => {
  const [progress, setProgress] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchProgress = async () => {
      try {
        setLoading(true);
        const data = await progressService.getUserOverallProgress();
        setProgress(data);
      } catch (err) {
        setProgress(null);
      } finally {
        setLoading(false);
      }
    };
    fetchProgress();
  }, []);

  if (loading) return <Loader label="Loading progress analytics..." />;

  return (
    <div>
      <PageHeader
        title="My Career Analytics & Progress"
        description="Comprehensive breakdown of completed skills, assignments, and mock interviews."
        breadcrumbs={[{ label: 'Progress' }]}
      />

      <div className="grid-3" style={{ marginBottom: '2rem' }}>
        <Card title="Overall Platform Completion">
          <h2 style={{ fontSize: '2.5rem', fontWeight: 800, color: 'var(--primary)' }}>
            {progress?.overall_progress_percentage || 0}%
          </h2>
        </Card>
        <Card title="Tasks Completed">
          <h2 style={{ fontSize: '2.5rem', fontWeight: 800, color: 'var(--accent-emerald)' }}>
            {progress?.completed_tasks || 0}
          </h2>
        </Card>
        <Card title="Interviews Passed">
          <h2 style={{ fontSize: '2.5rem', fontWeight: 800, color: 'var(--secondary)' }}>
            {progress?.completed_interviews || 0}
          </h2>
        </Card>
      </div>

      <Card title="Skill Competency Milestones">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem', marginBottom: '0.375rem' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>FastAPI & REST Architecture</span>
              <span style={{ color: 'var(--accent-emerald)' }}>85%</span>
            </div>
            <div style={{ width: '100%', height: '8px', background: 'var(--bg-input)', borderRadius: 'var(--radius-full)', overflow: 'hidden' }}>
              <div style={{ width: '85%', height: '100%', background: 'linear-gradient(90deg, var(--primary) 0%, var(--accent-emerald) 100%)' }} />
            </div>
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem', marginBottom: '0.375rem' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>PostgreSQL & SQLAlchemy ORM</span>
              <span style={{ color: 'var(--accent-emerald)' }}>75%</span>
            </div>
            <div style={{ width: '100%', height: '8px', background: 'var(--bg-input)', borderRadius: 'var(--radius-full)', overflow: 'hidden' }}>
              <div style={{ width: '75%', height: '100%', background: 'linear-gradient(90deg, var(--primary) 0%, var(--secondary) 100%)' }} />
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default ProgressPage;
