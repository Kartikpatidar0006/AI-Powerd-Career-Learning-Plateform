import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Video, Send, CheckCircle } from 'lucide-react';
import toast from 'react-hot-toast';
import PageHeader from '../components/PageHeader/PageHeader';
import Card from '../components/Card/Card';
import Textarea from '../components/Textarea/Textarea';
import Button from '../components/Button/Button';
import interviewService from '../services/interviewService';

export const InterviewPage = () => {
  const { interviewId } = useParams();
  const [started, setStarted] = useState(false);
  const [questions, setQuestions] = useState([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [answerText, setAnswerText] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleStartInterview = async () => {
    try {
      setLoading(true);
      const res = await interviewService.startInterview(interviewId);
      setQuestions(res.questions || []);
      setStarted(true);
    } catch (err) {
      toast.error('Failed to start interview.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitAnswer = async () => {
    const q = questions[currentIdx];
    if (!q) return;

    try {
      setLoading(true);
      await interviewService.answerQuestion(q.id, {
        answer_text: answerText,
        time_taken_seconds: 45,
      });
      toast.success('Answer recorded.');

      if (currentIdx + 1 < questions.length) {
        setCurrentIdx(currentIdx + 1);
        setAnswerText('');
      } else {
        await interviewService.finishInterview(interviewId);
        await interviewService.evaluateInterview(interviewId);
        toast.success('Interview completed!');
        navigate(`/interviews/${interviewId}/feedback`);
      }
    } catch (err) {
      toast.error('Failed to submit answer.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Mock Interview Session"
        description="Interactive evaluation interview session."
        breadcrumbs={[{ label: 'Interviews', path: '/interviews' }, { label: 'Interview Session' }]}
      />

      <div style={{ maxWidth: '800px' }}>
        {!started ? (
          <Card title="Mock Technical & Behavioral Interview Room">
            <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem', lineHeight: 1.6 }}>
              You will be presented with 5 questions (3 Technical, 2 Behavioral). Walk through your thought process, architecture decisions, and edge-case handling clearly.
            </p>
            <Button variant="primary" size="lg" icon={Video} isLoading={loading} onClick={handleStartInterview}>
              Begin Mock Interview
            </Button>
          </Card>
        ) : (
          <Card title={`Question ${currentIdx + 1} of ${questions.length}`}>
            <div style={{ marginBottom: '1.5rem' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.25rem 0.625rem', borderRadius: 'var(--radius-full)', background: 'var(--primary-light)', color: 'var(--primary)', textTransform: 'uppercase' }}>
                {questions[currentIdx]?.question_type || 'Technical'}
              </span>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-main)', marginTop: '0.75rem' }}>
                {questions[currentIdx]?.question}
              </h3>
            </div>

            <Textarea
              label="Your Answer / Thought Process"
              placeholder="Explain your approach, technical reasoning, and trade-offs step-by-step..."
              rows={6}
              value={answerText}
              onChange={(e) => setAnswerText(e.target.value)}
            />

            <Button variant="primary" size="lg" icon={Send} isLoading={loading} onClick={handleSubmitAnswer}>
              {currentIdx + 1 === questions.length ? 'Finish & Generate Feedback' : 'Next Question'}
            </Button>
          </Card>
        )}
      </div>
    </div>
  );
};

export default InterviewPage;
