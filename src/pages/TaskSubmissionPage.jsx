import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { Code, FileText, Send } from 'lucide-react';
import toast from 'react-hot-toast';
import PageHeader from '../components/PageHeader/PageHeader';
import Card from '../components/Card/Card';
import Input from '../components/Input/Input';
import Textarea from '../components/Textarea/Textarea';
import Button from '../components/Button/Button';
import taskService from '../services/taskService';

export const TaskSubmissionPage = () => {
  const { taskId } = useParams();
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm();

  const onSubmit = async (data) => {
    try {
      setSubmitting(true);
      const res = await taskService.submitTask(taskId, data);
      toast.success('Task submitted successfully!');
      
      // Auto trigger evaluation if submission created
      if (res && res.id) {
        try {
          await taskService.evaluateSubmission(res.id);
        } catch (evalErr) {
          // Silent evaluation fallback
        }
      }
      navigate(`/feedback/${taskId}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to submit task.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Submit Task Solution"
        description="Submit your solution for automated AI evaluation and feedback."
        breadcrumbs={[{ label: 'Tasks', path: '/tasks' }, { label: 'Submit Solution' }]}
      />

      <div style={{ maxWidth: '680px' }}>
        <Card>
          <form onSubmit={handleSubmit(onSubmit)}>
            <Input
              label="GitHub Repository URL (Optional)"
              type="url"
              placeholder="https://github.com/your-username/your-repo"
              icon={Code}
              error={errors.github_url?.message}
              {...register('github_url')}
            />

            <Textarea
              label="Submission Explanation / Code Snippets"
              placeholder="Detail your implementation, architecture decisions, and code solution here..."
              rows={6}
              error={errors.submission_text?.message}
              {...register('submission_text')}
            />

            <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
              <Button type="submit" variant="primary" size="lg" isLoading={submitting} icon={Send}>
                Submit for AI Evaluation
              </Button>
              <Button variant="secondary" size="lg" onClick={() => navigate(`/tasks/${taskId}`)}>
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
};

export default TaskSubmissionPage;
