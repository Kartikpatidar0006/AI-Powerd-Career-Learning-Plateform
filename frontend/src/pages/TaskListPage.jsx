import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckSquare, Clock, ArrowRight } from 'lucide-react';
import PageHeader from '../components/PageHeader/PageHeader';
import Card from '../components/Card/Card';
import Button from '../components/Button/Button';
import Loader from '../components/Loader/Loader';
import EmptyState from '../components/EmptyState/EmptyState';
import taskService from '../services/taskService';
import { formatDuration } from '../utils/formatters';

export const TaskListPage = () => {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchTasks = async () => {
      try {
        setLoading(true);
        const data = await taskService.getTasks();
        setTasks(Array.isArray(data) ? data : data.items || []);
      } catch (err) {
        setTasks([]);
      } finally {
        setLoading(false);
      }
    };
    fetchTasks();
  }, []);

  if (loading) return <Loader label="Loading learning tasks..." />;

  return (
    <div>
      <PageHeader
        title="Learning Tasks"
        description="Hands-on assignments and engineering tasks to build real-world experience."
        breadcrumbs={[{ label: 'Tasks' }]}
      />

      {tasks.length === 0 ? (
        <EmptyState title="No Tasks Available" message="There are currently no tasks listed." />
      ) : (
        <div className="grid-2">
          {tasks.map((task) => (
            <Card
              key={task.id}
              interactive
              title={task.title}
              subtitle={`Difficulty: ${task.difficulty || 'Medium'} • Est: ${formatDuration(task.estimated_minutes)}`}
              footer={
                <Button variant="primary" icon={ArrowRight} onClick={() => navigate(`/tasks/${task.id}`)}>
                  View Task Details
                </Button>
              }
            >
              <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                {task.description || 'Complete this task to gain hands-on technical experience.'}
              </p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default TaskListPage;
