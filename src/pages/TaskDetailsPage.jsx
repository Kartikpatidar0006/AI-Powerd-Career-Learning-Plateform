import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { FileText, Send, Award, Clock } from 'lucide-react';
import PageHeader from '../components/PageHeader/PageHeader';
import Card from '../components/Card/Card';
import Button from '../components/Button/Button';
import Loader from '../components/Loader/Loader';
import ErrorState from '../components/ErrorState/ErrorState';
import taskService from '../services/taskService';
import { formatDuration } from '../utils/formatters';

export const TaskDetailsPage = () => {
  const { taskId } = useParams();
  const [task, setTask] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchTask = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await taskService.getTaskById(taskId);
        setTask(data);
      } catch (err) {
        setError('Failed to load task details.');
      } finally {
        setLoading(false);
      }
    };
    fetchTask();
  }, [taskId]);

  if (loading) return <Loader label="Loading task details..." />;
  if (error || !task) return <ErrorState message={error || 'Task not found.'} />;

  return (
    <div>
      <PageHeader
        title={task.title}
        description={`Difficulty: ${task.difficulty || 'Medium'} • Estimated Time: ${formatDuration(task.estimated_minutes)}`}
        breadcrumbs={[{ label: 'Tasks', path: '/tasks' }, { label: task.title }]}
        action={
          <Button variant="primary" icon={Send} onClick={() => navigate(`/tasks/${taskId}/submit`)}>
            Submit Solution
          </Button>
        }
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <Card title="Task Description">
          <p style={{ fontSize: '0.9375rem', color: 'var(--text-main)', lineHeight: 1.6 }}>
            {task.description}
          </p>
        </Card>

        <Card title="Submission Instructions">
          <p style={{ fontSize: '0.9375rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
            {task.instructions || 'Provide your code solution via GitHub repository URL or written text response.'}
          </p>
        </Card>
      </div>
    </div>
  );
};

export default TaskDetailsPage;
