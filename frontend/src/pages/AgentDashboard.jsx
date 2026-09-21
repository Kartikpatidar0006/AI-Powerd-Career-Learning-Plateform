import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import {
  onboardStudent, getStudentDashboard,
  generateProblems, getStudentProblems, assignProblem,
  evaluateSubmission, getStudentEvaluations,
  startInterview, getCurrentQuestion, submitAnswer, getInterview,
  generateGuidance, getLatestGuidance,
} from '../services/agentService';

// ─── Step constants ───────────────────────────────────────────
const STEPS = [
  { id: 1, label: 'Profile', icon: '👤' },
  { id: 2, label: 'Problems', icon: '🧩' },
  { id: 3, label: 'Evaluate', icon: '🔍' },
  { id: 4, label: 'Interview', icon: '🎤' },
  { id: 5, label: 'Guidance', icon: '🚀' },
];

const PROFESSIONS = [
  'Full Stack Developer', 'Frontend Developer', 'Backend Developer',
  'Data Scientist', 'Machine Learning Engineer', 'DevOps Engineer',
  'Mobile Developer (React Native)', 'Cloud Engineer', 'UI/UX Designer',
  'Cybersecurity Engineer',
];

export default function AgentDashboard() {
  const [activeStep, setActiveStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [student, setStudent] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [problems, setProblems] = useState([]);
  const [evaluations, setEvaluations] = useState([]);
  const [activeInterview, setActiveInterview] = useState(null);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [answer, setAnswer] = useState('');
  const [lastFeedback, setLastFeedback] = useState(null);
  const [guidance, setGuidance] = useState(null);
  const [selectedEvalId, setSelectedEvalId] = useState('');

  // ── Form states ──
  const [profileForm, setProfileForm] = useState({
    full_name: '', email: '', profession: PROFESSIONS[0],
    experience_level: 'beginner', goals: '', preferred_stack: '', weekly_hours: 10,
  });
  const [githubUrl, setGithubUrl] = useState('');
  const [selectedProblemId, setSelectedProblemId] = useState('');
  const [problemDifficulty, setProblemDifficulty] = useState('medium');

  const stepComplete = (step) => {
    if (step === 1) return !!student;
    if (step === 2) return problems.length > 0;
    if (step === 3) return evaluations.length > 0 && evaluations.some(e => e.status === 'completed');
    if (step === 4) return !!activeInterview && activeInterview.status === 'completed';
    return !!guidance;
  };

  // ─── Agent 1: Onboard ─────────────────────────────────────────────────
  const handleOnboard = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await onboardStudent({ ...profileForm, weekly_hours: Number(profileForm.weekly_hours) });
      setStudent(data);
      const dash = await getStudentDashboard(data.id);
      setDashboard(dash.data);
      toast.success('✅ Profile created! Welcome to your AI Journey!');
      setActiveStep(2);
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Failed to create profile');
    } finally {
      setLoading(false);
    }
  };

  // ─── Agent 2: Generate problems ───────────────────────────────────────
  const handleGenerateProblems = async () => {
    if (!student) return;
    setLoading(true);
    try {
      const { data } = await generateProblems({
        student_id: student.id,
        difficulty: problemDifficulty,
        count: 3,
      });
      setProblems(prev => [...data, ...prev]);
      toast.success(`🧩 Generated ${data.length} ${problemDifficulty} problems!`);
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Problem generation failed');
    } finally {
      setLoading(false);
    }
  };

  // ─── Agent 3: Evaluate submission ─────────────────────────────────────
  const handleEvaluate = async (e) => {
    e.preventDefault();
    if (!student || !githubUrl) return;
    setLoading(true);
    toast.loading('🔍 Agent 3 is analyzing your GitHub repo…', { id: 'eval' });
    try {
      const { data } = await evaluateSubmission({
        student_id: student.id,
        github_url: githubUrl,
        problem_id: selectedProblemId || null,
      });
      setEvaluations(prev => [data, ...prev]);
      setSelectedEvalId(data.id);
      toast.dismiss('eval');
      toast.success(`🎯 Evaluation complete! Score: ${data.overall_score}/100`);
    } catch (err) {
      toast.dismiss('eval');
      toast.error(err?.response?.data?.error?.message || 'Evaluation failed');
    } finally {
      setLoading(false);
    }
  };

  // ─── Agent 4: Start & conduct interview ───────────────────────────────
  const handleStartInterview = async () => {
    if (!student || !selectedEvalId) {
      toast.error('Please select an evaluation first.');
      return;
    }
    setLoading(true);
    try {
      const { data: iv } = await startInterview({
        student_id: student.id,
        evaluation_id: selectedEvalId,
      });
      setActiveInterview(iv);
      const { data: q } = await getCurrentQuestion(iv.id);
      setCurrentQuestion(q);
      setLastFeedback(null);
      toast.success('🎤 Interview started! Good luck!');
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Could not start interview');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitAnswer = async () => {
    if (!answer.trim() || !activeInterview || !currentQuestion) return;
    setLoading(true);
    try {
      const { data: feedback } = await submitAnswer({
        interview_id: activeInterview.id,
        question_index: currentQuestion.question_index,
        answer,
      });
      setLastFeedback(feedback);
      setAnswer('');
      if (feedback.is_complete) {
        const { data: finalIv } = await getInterview(activeInterview.id);
        setActiveInterview(finalIv);
        setCurrentQuestion(null);
        toast.success(`🏆 Interview complete! Overall score: ${finalIv.overall_score}/100`);
      } else if (feedback.next_question) {
        setCurrentQuestion(prev => prev ? {
          ...prev,
          question_index: prev.question_index + 1,
          question: feedback.next_question,
          is_last: prev.question_index + 1 === prev.total_questions - 1,
        } : null);
      }
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Failed to submit answer');
    } finally {
      setLoading(false);
    }
  };

  // ─── Agent 5: Career guidance ─────────────────────────────────────────
  const handleGetGuidance = async () => {
    if (!student) return;
    setLoading(true);
    toast.loading('🚀 Agent 5 is building your career roadmap…', { id: 'guide' });
    try {
      const ivId = activeInterview?.id || null;
      const { data } = await generateGuidance(student.id, ivId);
      setGuidance(data);
      toast.dismiss('guide');
      toast.success(`🌟 Guidance ready! Career Readiness: ${data.readiness_score}%`);
    } catch (err) {
      toast.dismiss('guide');
      toast.error(err?.response?.data?.error?.message || 'Guidance generation failed');
    } finally {
      setLoading(false);
    }
  };

  const parseJson = (str) => {
    try { return JSON.parse(str || '[]'); } catch { return []; }
  };

  return (
    <div style={styles.page}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.headerInner}>
          <div style={styles.headerTitle}>
            <span style={styles.headerIcon}>🤖</span>
            <div>
              <h1 style={styles.h1}>AI Agent Dashboard</h1>
              <p style={styles.subtitle}>5 AI Agents guide your entire career journey</p>
            </div>
          </div>
          {student && (
            <div style={styles.studentBadge}>
              <span style={styles.studentAvatar}>{student.full_name[0]}</span>
              <div>
                <div style={styles.studentName}>{student.full_name}</div>
                <div style={styles.studentProf}>{student.profession}</div>
              </div>
            </div>
          )}
        </div>

        {/* Step Navigator */}
        <div style={styles.stepNav}>
          {STEPS.map((step, i) => (
            <React.Fragment key={step.id}>
              <button
                onClick={() => student && setActiveStep(step.id)}
                style={{
                  ...styles.stepBtn,
                  ...(activeStep === step.id ? styles.stepBtnActive : {}),
                  ...(stepComplete(step.id) ? styles.stepBtnDone : {}),
                  ...(!student && step.id > 1 ? styles.stepBtnDisabled : {}),
                }}
              >
                <span style={styles.stepIcon}>{stepComplete(step.id) ? '✅' : step.icon}</span>
                <span style={styles.stepLabel}>{step.label}</span>
                <span style={styles.stepNum}>Agent {step.id}</span>
              </button>
              {i < STEPS.length - 1 && <div style={styles.stepConnector} />}
            </React.Fragment>
          ))}
        </div>
      </div>

      <div style={styles.content}>
        {/* ─── STEP 1: Student Onboarding ────────────────────────── */}
        {activeStep === 1 && (
          <div style={styles.card}>
            <div style={styles.agentBadge}>🤖 Agent 1 — Student Onboarding</div>
            <h2 style={styles.cardTitle}>Tell me about yourself</h2>
            <p style={styles.cardDesc}>I'll create your personalized learning profile and dashboard.</p>

            <form onSubmit={handleOnboard} style={styles.form}>
              <div style={styles.formGrid}>
                <label style={styles.label}>
                  Full Name
                  <input
                    style={styles.input}
                    value={profileForm.full_name}
                    onChange={e => setProfileForm(p => ({ ...p, full_name: e.target.value }))}
                    placeholder="Your full name"
                    required
                  />
                </label>
                <label style={styles.label}>
                  Email
                  <input
                    style={styles.input}
                    type="email"
                    value={profileForm.email}
                    onChange={e => setProfileForm(p => ({ ...p, email: e.target.value }))}
                    placeholder="your@email.com"
                    required
                  />
                </label>
                <label style={styles.label}>
                  Target Profession
                  <select
                    style={styles.input}
                    value={profileForm.profession}
                    onChange={e => setProfileForm(p => ({ ...p, profession: e.target.value }))}
                  >
                    {PROFESSIONS.map(pr => <option key={pr}>{pr}</option>)}
                  </select>
                </label>
                <label style={styles.label}>
                  Experience Level
                  <select
                    style={styles.input}
                    value={profileForm.experience_level}
                    onChange={e => setProfileForm(p => ({ ...p, experience_level: e.target.value }))}
                  >
                    <option value="beginner">Beginner</option>
                    <option value="intermediate">Intermediate</option>
                    <option value="advanced">Advanced</option>
                  </select>
                </label>
                <label style={styles.label}>
                  Preferred Stack
                  <input
                    style={styles.input}
                    value={profileForm.preferred_stack}
                    onChange={e => setProfileForm(p => ({ ...p, preferred_stack: e.target.value }))}
                    placeholder="React, FastAPI, PostgreSQL..."
                  />
                </label>
                <label style={styles.label}>
                  Weekly Study Hours
                  <input
                    style={styles.input}
                    type="number"
                    min={1} max={80}
                    value={profileForm.weekly_hours}
                    onChange={e => setProfileForm(p => ({ ...p, weekly_hours: e.target.value }))}
                  />
                </label>
              </div>
              <label style={{ ...styles.label, gridColumn: '1/-1' }}>
                Career Goals
                <textarea
                  style={{ ...styles.input, height: 80, resize: 'vertical' }}
                  value={profileForm.goals}
                  onChange={e => setProfileForm(p => ({ ...p, goals: e.target.value }))}
                  placeholder="I want to land a job at a top tech company within 6 months..."
                />
              </label>
              <button type="submit" style={styles.btnPrimary} disabled={loading}>
                {loading ? '⏳ Creating profile...' : '🚀 Create My Profile'}
              </button>
            </form>

            {student && (
              <div style={styles.successBox}>
                <p>✅ <strong>Profile created!</strong> Welcome, {student.full_name}!</p>
                {dashboard && (
                  <div style={styles.statsRow}>
                    <div style={styles.statCard}><div style={styles.statVal}>{dashboard.total_problems_assigned}</div><div style={styles.statLabel}>Problems</div></div>
                    <div style={styles.statCard}><div style={styles.statVal}>{dashboard.total_evaluations}</div><div style={styles.statLabel}>Evaluations</div></div>
                    <div style={styles.statCard}><div style={styles.statVal}>{dashboard.average_score}%</div><div style={styles.statLabel}>Avg Score</div></div>
                    <div style={styles.statCard}><div style={styles.statVal}>{dashboard.latest_readiness_score}%</div><div style={styles.statLabel}>Readiness</div></div>
                  </div>
                )}
                <button style={styles.btnSecondary} onClick={() => setActiveStep(2)}>
                  Next: Generate Problems →
                </button>
              </div>
            )}
          </div>
        )}

        {/* ─── STEP 2: Problem Generation ────────────────────────── */}
        {activeStep === 2 && (
          <div style={styles.card}>
            <div style={styles.agentBadge}>🤖 Agent 2 — Problem Generation</div>
            <h2 style={styles.cardTitle}>Generate Your Practice Problems</h2>
            <p style={styles.cardDesc}>I'll create real-world problems tailored to your profession — {student?.profession}.</p>

            <div style={styles.diffRow}>
              {['easy', 'medium', 'hard'].map(d => (
                <button
                  key={d}
                  style={{ ...styles.diffBtn, ...(problemDifficulty === d ? styles.diffBtnActive : {}) }}
                  onClick={() => setProblemDifficulty(d)}
                >
                  {d === 'easy' ? '🟢' : d === 'medium' ? '🟡' : '🔴'} {d.charAt(0).toUpperCase() + d.slice(1)}
                </button>
              ))}
            </div>

            <button style={styles.btnPrimary} onClick={handleGenerateProblems} disabled={loading || !student}>
              {loading ? '⏳ Generating...' : `🧩 Generate 3 ${problemDifficulty} Problems`}
            </button>

            {problems.length > 0 && (
              <div style={styles.problemList}>
                {problems.map(p => (
                  <div key={p.id} style={styles.problemCard}>
                    <div style={styles.problemHeader}>
                      <span style={{ ...styles.diffTag, background: p.difficulty === 'easy' ? '#22c55e33' : p.difficulty === 'medium' ? '#f59e0b33' : '#ef444433', color: p.difficulty === 'easy' ? '#22c55e' : p.difficulty === 'medium' ? '#f59e0b' : '#ef4444' }}>
                        {p.difficulty.toUpperCase()}
                      </span>
                      <span style={styles.techTag}>{p.tech_stack}</span>
                      <span style={styles.hoursTag}>⏱ {p.estimated_hours}h</span>
                    </div>
                    <h3 style={styles.problemTitle}>{p.title}</h3>
                    <p style={styles.problemDesc}>{p.description.slice(0, 200)}...</p>
                    {parseJson(p.requirements).length > 0 && (
                      <ul style={styles.reqList}>
                        {parseJson(p.requirements).slice(0, 3).map((r, i) => <li key={i} style={styles.reqItem}>✓ {r}</li>)}
                      </ul>
                    )}
                    {!p.is_assigned && (
                      <button
                        style={styles.btnSmall}
                        onClick={async () => {
                          await assignProblem({ student_id: student.id, problem_id: p.id });
                          setProblems(prev => prev.map(x => x.id === p.id ? { ...x, is_assigned: true } : x));
                          setSelectedProblemId(p.id);
                          toast.success('Problem assigned!');
                        }}
                      >
                        📌 Assign This Problem
                      </button>
                    )}
                    {p.is_assigned && <span style={styles.assignedTag}>📌 Assigned</span>}
                  </div>
                ))}
              </div>
            )}

            {problems.length > 0 && (
              <button style={styles.btnSecondary} onClick={() => setActiveStep(3)}>
                Next: Submit & Evaluate →
              </button>
            )}
          </div>
        )}

        {/* ─── STEP 3: Evaluation ────────────────────────────────── */}
        {activeStep === 3 && (
          <div style={styles.card}>
            <div style={styles.agentBadge}>🤖 Agent 3 — Task Evaluation</div>
            <h2 style={styles.cardTitle}>Submit Your GitHub Repository</h2>
            <p style={styles.cardDesc}>I'll analyze your code quality, structure, and generate personalized interview questions.</p>

            <form onSubmit={handleEvaluate} style={styles.form}>
              <label style={styles.label}>
                GitHub Repository URL
                <input
                  style={styles.input}
                  type="url"
                  value={githubUrl}
                  onChange={e => setGithubUrl(e.target.value)}
                  placeholder="https://github.com/username/repo-name"
                  required
                />
              </label>
              {problems.length > 0 && (
                <label style={styles.label}>
                  Link to a Problem (optional)
                  <select style={styles.input} value={selectedProblemId} onChange={e => setSelectedProblemId(e.target.value)}>
                    <option value="">— Select a problem —</option>
                    {problems.map(p => <option key={p.id} value={p.id}>{p.title}</option>)}
                  </select>
                </label>
              )}
              <button type="submit" style={styles.btnPrimary} disabled={loading}>
                {loading ? '⏳ Evaluating your code...' : '🔍 Evaluate My Repository'}
              </button>
            </form>

            {evaluations.map(ev => (
              <div key={ev.id} style={{ ...styles.evalCard, border: selectedEvalId === ev.id ? '2px solid #818cf8' : '1px solid rgba(255,255,255,0.08)' }}>
                <div style={styles.evalHeader}>
                  <a href={ev.github_url} target="_blank" rel="noopener noreferrer" style={styles.repoLink}>
                    🔗 {ev.github_url.replace('https://github.com/', '')}
                  </a>
                  <span style={{ ...styles.statusBadge, background: ev.status === 'completed' ? '#22c55e22' : '#f59e0b22', color: ev.status === 'completed' ? '#22c55e' : '#f59e0b' }}>
                    {ev.status}
                  </span>
                </div>
                {ev.status === 'completed' && (
                  <>
                    <div style={styles.scoreGrid}>
                      {[
                        ['Code Quality', ev.code_quality_score],
                        ['Functionality', ev.functionality_score],
                        ['Documentation', ev.documentation_score],
                        ['Best Practices', ev.best_practices_score],
                        ['Overall', ev.overall_score],
                      ].map(([label, score]) => (
                        <div key={label} style={styles.scoreItem}>
                          <div style={styles.scoreLabel}>{label}</div>
                          <div style={styles.scoreBar}>
                            <div style={{ ...styles.scoreBarFill, width: `${score}%`, background: score >= 70 ? '#22c55e' : score >= 50 ? '#f59e0b' : '#ef4444' }} />
                          </div>
                          <div style={styles.scoreVal}>{score}/100</div>
                        </div>
                      ))}
                    </div>
                    {parseJson(ev.strengths).length > 0 && (
                      <div style={styles.feedbackSection}>
                        <strong style={{ color: '#22c55e' }}>✅ Strengths</strong>
                        <ul>{parseJson(ev.strengths).map((s, i) => <li key={i} style={styles.feedItem}>{s}</li>)}</ul>
                      </div>
                    )}
                    {parseJson(ev.improvements).length > 0 && (
                      <div style={styles.feedbackSection}>
                        <strong style={{ color: '#f59e0b' }}>⚠️ Improvements</strong>
                        <ul>{parseJson(ev.improvements).map((s, i) => <li key={i} style={styles.feedItem}>{s}</li>)}</ul>
                      </div>
                    )}
                    <div style={styles.qCount}>
                      📋 {parseJson(ev.interview_questions).length} interview questions generated
                    </div>
                    <button style={styles.btnSmall} onClick={() => { setSelectedEvalId(ev.id); setActiveStep(4); }}>
                      🎤 Start Interview with this Evaluation →
                    </button>
                  </>
                )}
              </div>
            ))}
          </div>
        )}

        {/* ─── STEP 4: AI Interview ──────────────────────────────── */}
        {activeStep === 4 && (
          <div style={styles.card}>
            <div style={styles.agentBadge}>🤖 Agent 4 — AI Mock Interview</div>
            <h2 style={styles.cardTitle}>Professional AI Interview</h2>
            <p style={styles.cardDesc}>I'll interview you based on questions generated from your project. Answer like you're in a real interview!</p>

            {!activeInterview && (
              <div>
                <label style={styles.label}>
                  Select Evaluation
                  <select style={styles.input} value={selectedEvalId} onChange={e => setSelectedEvalId(e.target.value)}>
                    <option value="">— Choose a completed evaluation —</option>
                    {evaluations.filter(e => e.status === 'completed').map(e => (
                      <option key={e.id} value={e.id}>{e.github_url.replace('https://github.com/', '')} ({e.overall_score}/100)</option>
                    ))}
                  </select>
                </label>
                <button style={styles.btnPrimary} onClick={handleStartInterview} disabled={loading || !selectedEvalId}>
                  {loading ? '⏳ Starting...' : '🎤 Start Interview'}
                </button>
              </div>
            )}

            {activeInterview && activeInterview.status === 'in_progress' && currentQuestion && (
              <div style={styles.interviewBox}>
                <div style={styles.interviewProgress}>
                  Question {currentQuestion.question_index + 1} of {currentQuestion.total_questions}
                  <div style={styles.progressBar}>
                    <div style={{ ...styles.progressFill, width: `${((currentQuestion.question_index) / currentQuestion.total_questions) * 100}%` }} />
                  </div>
                </div>
                <div style={styles.questionBox}>
                  <span style={styles.questionNum}>Q{currentQuestion.question_index + 1}</span>
                  <p style={styles.questionText}>{currentQuestion.question}</p>
                </div>
                {lastFeedback && (
                  <div style={styles.lastFeedback}>
                    <strong>Previous answer score: {lastFeedback.score}/100</strong>
                    <p style={{ color: '#94a3b8', margin: '4px 0 0' }}>{lastFeedback.feedback}</p>
                  </div>
                )}
                <textarea
                  style={{ ...styles.input, height: 140, resize: 'vertical', marginTop: 16 }}
                  value={answer}
                  onChange={e => setAnswer(e.target.value)}
                  placeholder="Type your answer here. Be specific and use examples from your project..."
                />
                <button style={styles.btnPrimary} onClick={handleSubmitAnswer} disabled={loading || !answer.trim()}>
                  {loading ? '⏳ Evaluating...' : currentQuestion.is_last ? '✅ Submit Final Answer' : '➡️ Submit & Next Question'}
                </button>
              </div>
            )}

            {activeInterview && activeInterview.status === 'completed' && (
              <div style={styles.interviewComplete}>
                <div style={styles.completeBadge}>🏆 Interview Complete!</div>
                <div style={styles.finalScores}>
                  {[
                    ['Technical', activeInterview.technical_score],
                    ['Communication', activeInterview.communication_score],
                    ['Confidence', activeInterview.confidence_score],
                    ['Overall', activeInterview.overall_score],
                  ].map(([label, score]) => (
                    <div key={label} style={styles.finalScore}>
                      <div style={{ ...styles.finalScoreVal, color: score >= 70 ? '#22c55e' : score >= 50 ? '#f59e0b' : '#ef4444' }}>{score}</div>
                      <div style={styles.finalScoreLabel}>{label}</div>
                    </div>
                  ))}
                </div>
                <button style={styles.btnSecondary} onClick={() => setActiveStep(5)}>
                  🚀 Get Career Guidance →
                </button>
              </div>
            )}
          </div>
        )}

        {/* ─── STEP 5: Career Guidance ───────────────────────────── */}
        {activeStep === 5 && (
          <div style={styles.card}>
            <div style={styles.agentBadge}>🤖 Agent 5 — Career Guidance</div>
            <h2 style={styles.cardTitle}>Your Personalized Career Roadmap</h2>
            <p style={styles.cardDesc}>I'll analyze your entire journey and provide a detailed career guidance report.</p>

            {!guidance && (
              <button style={styles.btnPrimary} onClick={handleGetGuidance} disabled={loading || !student}>
                {loading ? '⏳ Building your roadmap...' : '🚀 Generate My Career Guidance'}
              </button>
            )}

            {guidance && (
              <div style={styles.guidanceReport}>
                {/* Readiness Score */}
                <div style={styles.readinessBox}>
                  <div style={styles.readinessLabel}>Career Readiness Score</div>
                  <div style={{ ...styles.readinessScore, color: guidance.readiness_score >= 70 ? '#22c55e' : guidance.readiness_score >= 50 ? '#f59e0b' : '#ef4444' }}>
                    {guidance.readiness_score}%
                  </div>
                  <div style={styles.readinessBar}>
                    <div style={{ ...styles.readinessFill, width: `${guidance.readiness_score}%` }} />
                  </div>
                </div>

                {guidance.summary && (
                  <div style={styles.summaryBox}>
                    <h3 style={styles.sectionTitle}>📋 Summary</h3>
                    <p style={styles.summaryText}>{guidance.summary}</p>
                  </div>
                )}

                <div style={styles.guidanceGrid}>
                  {parseJson(guidance.strengths).length > 0 && (
                    <div style={styles.guideSection}>
                      <h3 style={{ ...styles.sectionTitle, color: '#22c55e' }}>✅ Strengths</h3>
                      {parseJson(guidance.strengths).map((s, i) => (
                        <div key={i} style={styles.guideItem}><span style={styles.dot}>●</span> {s}</div>
                      ))}
                    </div>
                  )}
                  {parseJson(guidance.weak_areas).length > 0 && (
                    <div style={styles.guideSection}>
                      <h3 style={{ ...styles.sectionTitle, color: '#f59e0b' }}>⚠️ Areas to Improve</h3>
                      {parseJson(guidance.weak_areas).map((s, i) => (
                        <div key={i} style={styles.guideItem}><span style={styles.dot}>●</span> {s}</div>
                      ))}
                    </div>
                  )}
                </div>

                {parseJson(guidance.next_steps).length > 0 && (
                  <div style={styles.guideSection}>
                    <h3 style={styles.sectionTitle}>🗺️ Next Steps</h3>
                    {parseJson(guidance.next_steps).map((s, i) => (
                      <div key={i} style={styles.stepItem}>
                        <span style={styles.stepBullet}>{i + 1}</span> {s}
                      </div>
                    ))}
                  </div>
                )}

                {parseJson(guidance.recommended_resources).length > 0 && (
                  <div style={styles.guideSection}>
                    <h3 style={styles.sectionTitle}>📚 Recommended Resources</h3>
                    {parseJson(guidance.recommended_resources).map((s, i) => (
                      <div key={i} style={styles.guideItem}><span style={styles.dot}>📖</span> {s}</div>
                    ))}
                  </div>
                )}

                {guidance.career_path_advice && (
                  <div style={styles.adviceBox}>
                    <h3 style={styles.sectionTitle}>🎯 Career Path Advice</h3>
                    <p style={styles.summaryText}>{guidance.career_path_advice}</p>
                  </div>
                )}

                <button style={styles.btnSecondary} onClick={() => { setGuidance(null); handleGetGuidance(); }}>
                  🔄 Regenerate Guidance
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles = {
  page: { minHeight: '100vh', background: 'linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%)', color: '#f8fafc', fontFamily: 'var(--font-main, Inter, sans-serif)' },
  header: { background: 'rgba(255,255,255,0.03)', borderBottom: '1px solid rgba(255,255,255,0.08)', padding: '24px 32px 0' },
  headerInner: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 },
  headerTitle: { display: 'flex', alignItems: 'center', gap: 16 },
  headerIcon: { fontSize: 48 },
  h1: { margin: 0, fontSize: 28, fontWeight: 700, background: 'linear-gradient(135deg, #818cf8, #c084fc)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' },
  subtitle: { margin: '4px 0 0', color: '#94a3b8', fontSize: 14 },
  studentBadge: { display: 'flex', alignItems: 'center', gap: 12, background: 'rgba(129,140,248,0.1)', border: '1px solid rgba(129,140,248,0.3)', borderRadius: 12, padding: '10px 16px' },
  studentAvatar: { width: 40, height: 40, borderRadius: '50%', background: 'linear-gradient(135deg, #818cf8, #c084fc)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, fontWeight: 700 },
  studentName: { fontWeight: 600, fontSize: 14 },
  studentProf: { color: '#818cf8', fontSize: 12 },
  stepNav: { display: 'flex', alignItems: 'center', gap: 0, overflowX: 'auto', paddingBottom: 0 },
  stepBtn: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, padding: '12px 20px', background: 'transparent', border: 'none', cursor: 'pointer', color: '#64748b', borderBottom: '3px solid transparent', transition: 'all 0.2s', minWidth: 90 },
  stepBtnActive: { color: '#818cf8', borderBottom: '3px solid #818cf8' },
  stepBtnDone: { color: '#22c55e', borderBottom: '3px solid #22c55e' },
  stepBtnDisabled: { opacity: 0.4, cursor: 'not-allowed' },
  stepIcon: { fontSize: 22 },
  stepLabel: { fontSize: 12, fontWeight: 600 },
  stepNum: { fontSize: 10, opacity: 0.6 },
  stepConnector: { width: 24, height: 2, background: 'rgba(255,255,255,0.1)', flexShrink: 0 },
  content: { maxWidth: 800, margin: '0 auto', padding: '32px 16px' },
  card: { background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 20, padding: 32 },
  agentBadge: { display: 'inline-flex', background: 'rgba(129,140,248,0.15)', border: '1px solid rgba(129,140,248,0.4)', borderRadius: 20, padding: '4px 14px', fontSize: 13, color: '#a5b4fc', marginBottom: 16 },
  cardTitle: { fontSize: 24, fontWeight: 700, margin: '0 0 8px' },
  cardDesc: { color: '#94a3b8', margin: '0 0 24px', fontSize: 14, lineHeight: 1.6 },
  form: { display: 'flex', flexDirection: 'column', gap: 16 },
  formGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 },
  label: { display: 'flex', flexDirection: 'column', gap: 6, fontSize: 13, fontWeight: 500, color: '#94a3b8' },
  input: { marginTop: 4, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 10, padding: '10px 14px', color: '#f8fafc', fontSize: 14, outline: 'none', width: '100%', boxSizing: 'border-box' },
  btnPrimary: { background: 'linear-gradient(135deg, #818cf8, #c084fc)', border: 'none', borderRadius: 12, padding: '13px 28px', color: '#fff', fontWeight: 700, fontSize: 15, cursor: 'pointer', marginTop: 8, transition: 'opacity 0.2s' },
  btnSecondary: { background: 'rgba(129,140,248,0.15)', border: '1px solid rgba(129,140,248,0.4)', borderRadius: 12, padding: '11px 24px', color: '#a5b4fc', fontWeight: 600, fontSize: 14, cursor: 'pointer', marginTop: 16 },
  btnSmall: { background: 'rgba(129,140,248,0.2)', border: '1px solid rgba(129,140,248,0.3)', borderRadius: 8, padding: '7px 14px', color: '#a5b4fc', fontSize: 12, fontWeight: 600, cursor: 'pointer', marginTop: 10 },
  successBox: { marginTop: 24, background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.3)', borderRadius: 14, padding: 20 },
  statsRow: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, margin: '16px 0' },
  statCard: { background: 'rgba(255,255,255,0.04)', borderRadius: 10, padding: '12px 8px', textAlign: 'center' },
  statVal: { fontSize: 24, fontWeight: 700, color: '#818cf8' },
  statLabel: { fontSize: 11, color: '#64748b', marginTop: 4 },
  diffRow: { display: 'flex', gap: 12, marginBottom: 20 },
  diffBtn: { flex: 1, background: 'rgba(255,255,255,0.04)', border: '2px solid rgba(255,255,255,0.1)', borderRadius: 10, padding: '10px', color: '#94a3b8', cursor: 'pointer', fontWeight: 600, fontSize: 14, transition: 'all 0.2s' },
  diffBtnActive: { borderColor: '#818cf8', color: '#818cf8', background: 'rgba(129,140,248,0.1)' },
  problemList: { display: 'flex', flexDirection: 'column', gap: 16, marginTop: 24 },
  problemCard: { background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 14, padding: 20 },
  problemHeader: { display: 'flex', gap: 10, alignItems: 'center', marginBottom: 10 },
  diffTag: { borderRadius: 6, padding: '3px 10px', fontSize: 11, fontWeight: 700 },
  techTag: { color: '#64748b', fontSize: 12, marginLeft: 'auto' },
  hoursTag: { color: '#64748b', fontSize: 12 },
  problemTitle: { margin: '0 0 8px', fontSize: 16, fontWeight: 700 },
  problemDesc: { color: '#94a3b8', fontSize: 13, lineHeight: 1.6, margin: 0 },
  reqList: { margin: '10px 0 0', padding: 0, listStyle: 'none' },
  reqItem: { color: '#22c55e', fontSize: 13, marginBottom: 4 },
  assignedTag: { display: 'inline-block', marginTop: 10, color: '#818cf8', fontSize: 13 },
  evalCard: { background: 'rgba(255,255,255,0.03)', borderRadius: 14, padding: 20, marginTop: 20 },
  evalHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 },
  repoLink: { color: '#818cf8', fontSize: 13, textDecoration: 'none' },
  statusBadge: { borderRadius: 20, padding: '3px 12px', fontSize: 12, fontWeight: 600 },
  scoreGrid: { display: 'flex', flexDirection: 'column', gap: 10 },
  scoreItem: { display: 'grid', gridTemplateColumns: '140px 1fr 60px', gap: 10, alignItems: 'center', fontSize: 13 },
  scoreLabel: { color: '#94a3b8' },
  scoreBar: { height: 6, background: 'rgba(255,255,255,0.1)', borderRadius: 3, overflow: 'hidden' },
  scoreBarFill: { height: '100%', borderRadius: 3, transition: 'width 0.5s' },
  scoreVal: { textAlign: 'right', fontWeight: 600, fontSize: 13 },
  feedbackSection: { marginTop: 14, fontSize: 13 },
  feedItem: { color: '#94a3b8', marginBottom: 4 },
  qCount: { marginTop: 14, color: '#818cf8', fontSize: 13 },
  interviewBox: { display: 'flex', flexDirection: 'column', gap: 0 },
  interviewProgress: { fontSize: 13, color: '#94a3b8', marginBottom: 12 },
  progressBar: { height: 4, background: 'rgba(255,255,255,0.1)', borderRadius: 2, overflow: 'hidden', marginTop: 6 },
  progressFill: { height: '100%', background: 'linear-gradient(90deg, #818cf8, #c084fc)', borderRadius: 2, transition: 'width 0.4s' },
  questionBox: { background: 'rgba(129,140,248,0.08)', border: '1px solid rgba(129,140,248,0.2)', borderRadius: 14, padding: 20, display: 'flex', gap: 14, alignItems: 'flex-start' },
  questionNum: { background: 'rgba(129,140,248,0.3)', borderRadius: 8, padding: '4px 10px', fontSize: 12, fontWeight: 700, color: '#a5b4fc', whiteSpace: 'nowrap' },
  questionText: { margin: 0, fontSize: 16, lineHeight: 1.6, fontWeight: 500 },
  lastFeedback: { background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: 10, padding: '12px 16px', fontSize: 13 },
  interviewComplete: { textAlign: 'center', padding: '20px 0' },
  completeBadge: { fontSize: 28, fontWeight: 700, marginBottom: 20 },
  finalScores: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 },
  finalScore: { background: 'rgba(255,255,255,0.04)', borderRadius: 14, padding: '16px 8px' },
  finalScoreVal: { fontSize: 36, fontWeight: 800 },
  finalScoreLabel: { fontSize: 12, color: '#64748b', marginTop: 4 },
  guidanceReport: { display: 'flex', flexDirection: 'column', gap: 20 },
  readinessBox: { background: 'rgba(129,140,248,0.08)', border: '1px solid rgba(129,140,248,0.2)', borderRadius: 14, padding: 24, textAlign: 'center' },
  readinessLabel: { color: '#94a3b8', fontSize: 13, marginBottom: 8 },
  readinessScore: { fontSize: 56, fontWeight: 800, lineHeight: 1 },
  readinessBar: { height: 8, background: 'rgba(255,255,255,0.1)', borderRadius: 4, overflow: 'hidden', marginTop: 16 },
  readinessFill: { height: '100%', background: 'linear-gradient(90deg, #818cf8, #22c55e)', borderRadius: 4 },
  summaryBox: { background: 'rgba(255,255,255,0.03)', borderRadius: 14, padding: 20 },
  sectionTitle: { fontSize: 16, fontWeight: 700, margin: '0 0 12px' },
  summaryText: { color: '#94a3b8', fontSize: 14, lineHeight: 1.7, margin: 0 },
  guidanceGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 },
  guideSection: { background: 'rgba(255,255,255,0.03)', borderRadius: 14, padding: 20 },
  guideItem: { fontSize: 14, color: '#cbd5e1', marginBottom: 8, display: 'flex', gap: 8 },
  dot: { color: '#818cf8', flexShrink: 0 },
  stepItem: { display: 'flex', gap: 12, alignItems: 'flex-start', marginBottom: 10, fontSize: 14, color: '#cbd5e1' },
  stepBullet: { background: 'rgba(129,140,248,0.3)', color: '#a5b4fc', borderRadius: '50%', width: 24, height: 24, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, flexShrink: 0 },
  adviceBox: { background: 'rgba(192,132,252,0.08)', border: '1px solid rgba(192,132,252,0.2)', borderRadius: 14, padding: 20 },
};
