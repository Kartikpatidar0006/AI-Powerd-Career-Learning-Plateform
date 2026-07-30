import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Video, Calendar, ArrowRight } from 'lucide-react';
import PageHeader from '../components/PageHeader/PageHeader';
import Card from '../components/Card/Card';
import Button from '../components/Button/Button';
import Loader from '../components/Loader/Loader';
import EmptyState from '../components/EmptyState/EmptyState';
import interviewService from '../services/interviewService';
import { formatDateTime } from '../utils/formatters';

export const InterviewListPage = () => {
  const [interviews, setInterviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchInterviews = async () => {
      try {
        setLoading(true);
        const data = await interviewService.getMyInterviews();
        setInterviews(Array.isArray(data) ? data : data.items || []);
      } catch (err) {
        setInterviews([]);
      } finally {
        setLoading(false);
      }
    };
    fetchInterviews();
  }, []);

  if (loading) return <Loader label="Loading scheduled mock interviews..." />;

  return (
    <div>
      <PageHeader
        title="Mock Technical Interviews"
        description="Simulated technical and behavioral interviews powered by automated evaluation."
        breadcrumbs={[{ label: 'Interviews' }]}
      />

      {interviews.length === 0 ? (
        <EmptyState
          title="No Interviews Scheduled"
          message="Complete a task with 70%+ score to automatically unlock an interview session!"
          actionLabel="View Tasks"
          onAction={() => navigate('/tasks')}
        />
      ) : (
        <div className="grid-2">
          {interviews.map((item) => (
            <Card
              key={item.id}
              interactive
              title="Mock Technical Interview"
              subtitle={`Status: ${item.status} • Duration: ${item.duration_minutes || 10} mins`}
              footer={
                <Button variant="primary" icon={ArrowRight} onClick={() => navigate(`/interviews/${item.id}`)}>
                  Enter Interview Room
                </Button>
              }
            >
              <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                Scheduled for: {formatDateTime(item.scheduled_at)}
              </p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default InterviewListPage;
