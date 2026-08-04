import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Video, Sparkles, ShieldCheck, Cpu, Mic, FileText, ArrowRight } from 'lucide-react';
import toast from 'react-hot-toast';
import PageHeader from '../components/PageHeader/PageHeader';
import Card from '../components/Card/Card';
import Button from '../components/Button/Button';
import Loader from '../components/Loader/Loader';
import AIInterviewerRoom from '../components/Interview/AIInterviewerRoom';
import interviewService from '../services/interviewService';
import userService from '../services/userService';

export const InterviewPage = () => {
  const { interviewId } = useParams();
  const [started, setStarted] = useState(false);
  const [questions, setQuestions] = useState([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [userProfession, setUserProfession] = useState('Software Engineering');
  const navigate = useNavigate();

  useEffect(() => {
    userService
      .getProfile()
      .then((res) => {
        if (res?.profession?.name) {
          setUserProfession(res.profession.name);
        }
      })
      .catch(() => {});
  }, []);

  const handleStartInterview = async () => {
    try {
      setLoading(true);
      const res = await interviewService.startInterview(interviewId);
      setQuestions(res.questions || []);
      setStarted(true);
      toast.success('AI Interview Room initialized. Microphone & Voice Synthesis active.');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to initialize AI interview room.');
    } finally {
      setLoading(false);
    }
  };

  const handleAnswerSubmit = async (answerText) => {
    const q = questions[currentIdx];
    if (!q) return;

    try {
      setSubmitting(true);
      await interviewService.answerQuestion(q.id, {
        answer_text: answerText,
        time_taken_seconds: 60,
      });

      toast.success('Answer recorded by AI examiner.');

      if (currentIdx + 1 < questions.length) {
        setCurrentIdx((prev) => prev + 1);
      } else {
        toast.loading('Generating comprehensive AI evaluation report...');
        await interviewService.finishInterview(interviewId);
        await interviewService.evaluateInterview(interviewId);
        toast.dismiss();
        toast.success('AI Evaluation Report Ready!');
        navigate(`/interviews/${interviewId}/feedback`);
      }
    } catch (err) {
      toast.error('Failed to submit answer to AI examiner.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRequestFollowup = async (questionId, currentAnswerText) => {
    try {
      toast.loading('AI Examiner formulating follow-up probe...');
      const followup = await interviewService.generateFollowup(interviewId, questionId, currentAnswerText || 'General response');
      toast.dismiss();
      toast.success('Follow-up question generated!');
      setQuestions((prev) => [...prev, followup]);
      setCurrentIdx(questions.length); // Jump to new follow-up
    } catch {
      toast.dismiss();
      toast.error('Could not generate follow-up question.');
    }
  };

  if (loading) {
    return <Loader label="Initializing AI Recruiter Engine & Speech Synthesis..." />;
  }

  return (
    <div>
      <PageHeader
        title="Live AI Mock Interview Room"
        description="Real-time voice, video & code technical interview powered by artificial intelligence."
        breadcrumbs={[{ label: 'Interviews', path: '/interviews' }, { label: 'Live AI Session' }]}
      />

      <div style={{ maxWidth: '1100px', margin: '0 auto' }}>
        {!started ? (
          <Card
            style={{
              background: 'linear-gradient(135deg, rgba(15,23,42,0.95) 0%, rgba(99,102,241,0.2) 100%)',
              border: '1px solid var(--primary-glow)',
              padding: '2.5rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--primary)', fontWeight: 800, fontSize: '0.875rem', marginBottom: '0.75rem' }}>
              <Sparkles size={18} /> REAL-TIME VOICE & VIDEO EVALUATION
            </div>
            <h2 style={{ fontSize: '2rem', fontWeight: 900, color: 'var(--text-main)', marginBottom: '1rem', fontFamily: 'var(--font-heading)' }}>
              Enter the AI Recruiter Interview Studio
            </h2>

            <p style={{ color: 'var(--text-muted)', fontSize: '1rem', lineHeight: 1.6, marginBottom: '2rem', maxWidth: '750px' }}>
              Experience a realistic, interactive interview with our AI Examiner. The AI will speak questions aloud, evaluate your verbal answers in real-time, analyze body language & eye contact, and provide a live coding workspace for technical challenges.
            </p>

            <div className="grid-3" style={{ gap: '1.25rem', marginBottom: '2.5rem' }}>
              <div style={{ padding: '1rem', background: 'rgba(255,255,255,0.05)', borderRadius: '0.5rem', border: '1px solid rgba(255,255,255,0.1)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#10B981', fontWeight: 700, marginBottom: '0.375rem' }}>
                  <Mic size={18} /> Voice Synthesis (TTS & STT)
                </div>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                  AI speaks questions aloud. Speak your answers via microphone for speech-to-text transcription.
                </p>
              </div>

              <div style={{ padding: '1rem', background: 'rgba(255,255,255,0.05)', borderRadius: '0.5rem', border: '1px solid rgba(255,255,255,0.1)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#38BDF8', fontWeight: 700, marginBottom: '0.375rem' }}>
                  <ShieldCheck size={18} /> Vision & Body Analytics
                </div>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                  Live webcam HUD tracking confidence %, eye contact focus, and speaking pace.
                </p>
              </div>

              <div style={{ padding: '1rem', background: 'rgba(255,255,255,0.05)', borderRadius: '0.5rem', border: '1px solid rgba(255,255,255,0.1)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#C084FC', fontWeight: 700, marginBottom: '0.375rem' }}>
                  <Cpu size={18} /> Code Editor Workspace
                </div>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                  Integrated IDE studio to write, execute, and test code for technical algorithmic questions.
                </p>
              </div>
            </div>

            <Button variant="primary" size="lg" icon={Video} isLoading={loading} onClick={handleStartInterview}>
              Start AI Voice & Video Interview
            </Button>
          </Card>
        ) : (
          <AIInterviewerRoom
            question={questions[currentIdx]}
            questionIndex={currentIdx}
            totalQuestions={questions.length}
            onAnswerSubmit={handleAnswerSubmit}
            onRequestFollowup={handleRequestFollowup}
            isSubmitting={submitting}
            professionName={userProfession}
          />
        )}
      </div>
    </div>
  );
};

export default InterviewPage;
