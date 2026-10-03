/**
 * EvaluationResultPage — Dedicated page showing detailed evaluation results for a task.
 *
 * Route: /evaluations/:taskId
 *
 * Displays:
 * - Pass/Fail badge with score ring
 * - Readable mentor feedback summary
 * - Itemized deterministic check breakdown with points and pass/fail indicators
 * - AI code quality strengths, weaknesses, and improvement suggestions
 * - Action buttons to continue to next task or re-submit
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import AppNavbar from '../components/AppNavbar';
import { getEvaluationForTask } from '../services/evaluator';
import type { EvaluationResult, CheckResultResponse } from '../services/evaluator';
import { getSession } from '../services/interview';
import type { InterviewSessionResponse } from '../types/interview';

function ScoreRing({ score, passed }: { score: number; passed: boolean }) {
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = passed ? '#34d399' : '#f87171';

  return (
    <div className="relative w-32 h-32 flex-shrink-0">
      <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
        <circle cx="50" cy="50" r={radius} fill="none" stroke="#1e293b" strokeWidth="10" />
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 1s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold font-mono" style={{ color }}>
          {Math.round(score)}
        </span>
        <span className="text-xs text-surface-400 font-semibold">out of 100</span>
      </div>
    </div>
  );
}

export default function EvaluationResultPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const [evaluation, setEvaluation] = useState<EvaluationResult | null>(null);
  const [interviewSession, setInterviewSession] = useState<InterviewSessionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!taskId) return;
    const fetchEval = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await getEvaluationForTask(taskId);
        setEvaluation(data);

        // Check if an interview session was created for this evaluated task
        try {
          const sessionData = await getSession(taskId);
          setInterviewSession(sessionData);
        } catch {
          setInterviewSession(null);
        }
      } catch (err: unknown) {
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setError(detail || 'Failed to load evaluation result.');
      } finally {
        setLoading(false);
      }
    };
    fetchEval();
  }, [taskId]);

  return (
    <div className="min-h-screen bg-surface-950 text-surface-100">
      <AppNavbar />
      <main className="max-w-3xl mx-auto px-4 py-8">
        {/* Navigation back */}
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={() => navigate('/tasks')}
            className="inline-flex items-center gap-2 text-sm text-surface-400 hover:text-surface-200 transition-colors"
          >
            ← Back to Daily Tasks
          </button>
          <button
            onClick={() => navigate('/history')}
            className="text-sm text-primary-400 hover:underline"
          >
            Task History →
          </button>
        </div>

        {/* Loading state */}
        {loading && (
          <div className="p-12 text-center space-y-4">
            <div className="w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-surface-400 text-sm">Loading evaluation report…</p>
          </div>
        )}

        {/* Error state */}
        {!loading && error && (
          <div className="p-6 rounded-2xl bg-danger-500/10 border border-danger-500/30 text-center space-y-3">
            <span className="text-3xl">⚠️</span>
            <h2 className="text-lg font-bold text-danger-300">Unable to Load Evaluation</h2>
            <p className="text-sm text-surface-400">{error}</p>
            <button
              onClick={() => navigate('/tasks')}
              className="mt-2 px-5 py-2 rounded-xl bg-surface-800 text-surface-200 hover:bg-surface-700 text-sm font-medium transition-colors"
            >
              Return to Daily Tasks
            </button>
          </div>
        )}

        {/* Content */}
        {!loading && evaluation && (
          <div className="space-y-6">
            {/* Header Card */}
            <div
              className={`p-6 md:p-8 rounded-3xl border shadow-xl ${
                evaluation.passed
                  ? 'bg-gradient-to-br from-emerald-950/40 via-surface-900 to-surface-950 border-emerald-500/30 shadow-emerald-950/20'
                  : 'bg-gradient-to-br from-red-950/40 via-surface-900 to-surface-950 border-red-500/30 shadow-red-950/20'
              }`}
            >
              <div className="flex flex-col sm:flex-row items-center sm:items-start gap-6">
                {evaluation.final_score !== null && (
                  <ScoreRing score={evaluation.final_score} passed={!!evaluation.passed} />
                )}
                <div className="flex-1 text-center sm:text-left space-y-2">
                  <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider mb-1"
                    style={{
                      backgroundColor: evaluation.passed ? 'rgba(52, 211, 153, 0.15)' : 'rgba(248, 113, 113, 0.15)',
                      color: evaluation.passed ? '#34d399' : '#f87171',
                      border: `1px solid ${evaluation.passed ? 'rgba(52, 211, 153, 0.3)' : 'rgba(248, 113, 113, 0.3)'}`,
                    }}
                  >
                    <span>{evaluation.passed ? '✓ PASSED' : '✗ NEEDS IMPROVEMENT'}</span>
                  </div>
                  <h1 className="text-2xl md:text-3xl font-extrabold text-surface-100">
                    {evaluation.passed ? 'Task Complete!' : 'Task Needs Work'}
                  </h1>
                  <p className="text-surface-300 text-sm md:text-base leading-relaxed">
                    {evaluation.feedback_summary || 'Evaluation completed.'}
                  </p>
                  {evaluation.github_repo_url && (
                    <div className="pt-2 text-xs text-surface-400">
                      Evaluated repository:{' '}
                      <a
                        href={evaluation.github_repo_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary-400 hover:underline font-mono"
                      >
                        {evaluation.github_repo_url}
                      </a>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Deterministic Code Review Checks */}
            {evaluation.deterministic_checks && evaluation.deterministic_checks.length > 0 && (
              <div className="p-6 rounded-2xl bg-surface-900/90 border border-surface-800 space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-bold text-surface-100 flex items-center gap-2">
                    <span>🔍</span> Static Code & Repository Checks
                  </h2>
                  {evaluation.deterministic_score !== null && (
                    <span className="text-xs font-mono text-surface-400 bg-surface-800 px-2.5 py-1 rounded-full">
                      Deterministic: {evaluation.deterministic_score.toFixed(0)} / 100 (weight: 65%)
                    </span>
                  )}
                </div>
                <div className="space-y-2.5">
                  {evaluation.deterministic_checks.map((check: CheckResultResponse, idx: number) => (
                    <div
                      key={idx}
                      className={`p-3.5 rounded-xl border flex items-start gap-3 transition-colors ${
                        check.passed
                          ? 'bg-emerald-500/5 border-emerald-500/20 text-surface-200'
                          : 'bg-red-500/5 border-red-500/20 text-surface-200'
                      }`}
                    >
                      <span
                        className={`text-lg font-bold flex-shrink-0 mt-0.5 ${
                          check.passed ? 'text-emerald-400' : 'text-red-400'
                        }`}
                      >
                        {check.passed ? '✓' : '✗'}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="font-semibold text-sm capitalize">
                            {check.check_name.replace(/_/g, ' ')}
                          </span>
                          <span
                            className={`text-xs font-mono font-bold ${
                              check.passed ? 'text-emerald-400' : 'text-surface-500'
                            }`}
                          >
                            {check.score_contribution.toFixed(1)} / {check.weight_pct.toFixed(0)} pts
                          </span>
                        </div>
                        <p className="text-xs text-surface-400 leading-relaxed">{check.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* LLM Qualitative Review Section */}
            {(evaluation.llm_strengths?.length ||
              evaluation.llm_weaknesses?.length ||
              evaluation.llm_suggestions?.length) && (
              <div className="p-6 rounded-2xl bg-surface-900/90 border border-surface-800 space-y-5">
                <h2 className="text-base font-bold text-surface-100 flex items-center gap-2">
                  <span>🤖</span> AI Mentor Review Insights
                </h2>
                <div className="grid gap-4 md:grid-cols-3">
                  {evaluation.llm_strengths && evaluation.llm_strengths.length > 0 && (
                    <div className="p-4 rounded-xl bg-surface-950/60 border border-emerald-500/20 space-y-2">
                      <h3 className="text-xs font-bold text-emerald-400 uppercase tracking-widest flex items-center gap-1.5">
                        <span>💪</span> Strengths
                      </h3>
                      <ul className="space-y-1.5 text-xs text-surface-300">
                        {evaluation.llm_strengths.map((s, i) => (
                          <li key={i} className="flex items-start gap-1.5">
                            <span className="text-emerald-400 font-bold">•</span>
                            <span>{s}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {evaluation.llm_weaknesses && evaluation.llm_weaknesses.length > 0 && (
                    <div className="p-4 rounded-xl bg-surface-950/60 border border-amber-500/20 space-y-2">
                      <h3 className="text-xs font-bold text-amber-400 uppercase tracking-widest flex items-center gap-1.5">
                        <span>⚠️</span> Areas for Growth
                      </h3>
                      <ul className="space-y-1.5 text-xs text-surface-300">
                        {evaluation.llm_weaknesses.map((w, i) => (
                          <li key={i} className="flex items-start gap-1.5">
                            <span className="text-amber-400 font-bold">•</span>
                            <span>{w}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {evaluation.llm_suggestions && evaluation.llm_suggestions.length > 0 && (
                    <div className="p-4 rounded-xl bg-surface-950/60 border border-sky-500/20 space-y-2">
                      <h3 className="text-xs font-bold text-sky-400 uppercase tracking-widest flex items-center gap-1.5">
                        <span>💡</span> Mentor Suggestions
                      </h3>
                      <ul className="space-y-1.5 text-xs text-surface-300">
                        {evaluation.llm_suggestions.map((s, i) => (
                          <li key={i} className="flex items-start gap-1.5">
                            <span className="text-sky-400 font-bold">•</span>
                            <span>{s}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Bottom Actions */}
            <div className="flex flex-col sm:flex-row items-center justify-end gap-3 pt-2">
              <button
                onClick={() => navigate('/tasks')}
                className="w-full sm:w-auto px-6 py-3 rounded-xl bg-surface-800 text-surface-200 hover:bg-surface-700 font-semibold text-sm transition-colors"
              >
                Back to Daily Task
              </button>

              {/* AI Mock Interview CTA if session is available or in progress */}
              {interviewSession && (interviewSession.status === 'AVAILABLE' || interviewSession.status === 'IN_PROGRESS') && (
                <button
                  id="take-interview-btn"
                  onClick={() => navigate(`/interview/${taskId}`)}
                  className="w-full sm:w-auto px-6 py-3 rounded-xl bg-gradient-to-r from-purple-500 to-indigo-600 text-white font-semibold text-sm hover:from-purple-400 hover:to-indigo-500 transition-all shadow-lg shadow-purple-500/25 flex items-center justify-center gap-2"
                >
                  <span>🤖</span>
                  <span>
                    {interviewSession.status === 'IN_PROGRESS'
                      ? 'Resume Mock Interview →'
                      : 'Take AI Mock Interview →'}
                  </span>
                </button>
              )}

              {evaluation.passed ? (
                <button
                  onClick={() => navigate('/tasks')}
                  className="w-full sm:w-auto px-8 py-3 rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 text-white font-semibold text-sm hover:from-emerald-400 hover:to-emerald-500 transition-all shadow-lg shadow-emerald-500/25"
                >
                  Proceed to Next Task →
                </button>
              ) : (
                <button
                  onClick={() => navigate('/tasks')}
                  className="w-full sm:w-auto px-8 py-3 rounded-xl bg-gradient-to-r from-primary-500 to-primary-600 text-white font-semibold text-sm hover:from-primary-400 hover:to-primary-500 transition-all shadow-lg shadow-primary-500/25"
                >
                  Improve & Re-submit Task →
                </button>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
