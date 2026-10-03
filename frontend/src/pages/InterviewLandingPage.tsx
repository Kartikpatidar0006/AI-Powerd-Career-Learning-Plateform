/**
 * InterviewLandingPage — Landing screen for starting, resuming, or reviewing an interview.
 *
 * Route: /interview/:taskId
 *
 * States handled:
 * - Loading / Error
 * - 404: No session yet (task not yet evaluated)
 * - AVAILABLE: Instructions, time remaining countdown, "Start Interview" button
 * - IN_PROGRESS: "Resume Interview" button with violation warnings
 * - COMPLETED: Concluded summary with link to results
 * - EXPIRED: Non-technical expiry notice with link back to tasks
 * - TERMINATED_VIOLATION: Clear explanation of violation termination
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import AppNavbar from '../components/AppNavbar';
import { getSession } from '../services/interview';
import type { InterviewSessionResponse } from '../types/interview';

function formatRemainingTime(seconds: number): string {
  if (seconds <= 0) return 'Expired';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) {
    return `${hours}h ${minutes}m remaining`;
  }
  return `${minutes}m remaining`;
}

export default function InterviewLandingPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();

  const [session, setSession] = useState<InterviewSessionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessionNotFound, setSessionNotFound] = useState(false);

  useEffect(() => {
    if (!taskId) return;

    let mounted = true;
    const fetchSession = async () => {
      try {
        setLoading(true);
        setError(null);
        setSessionNotFound(false);
        const data = await getSession(taskId);
        if (!mounted) return;

        if (data === null) {
          setSessionNotFound(true);
        } else {
          setSession(data);
        }
      } catch (err: unknown) {
        if (!mounted) return;
        const msg = err instanceof Error ? err.message : 'Failed to load interview session';
        setError(msg);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    fetchSession();
    return () => {
      mounted = false;
    };
  }, [taskId]);

  return (
    <div className="min-h-screen bg-surface-950 text-surface-100">
      <AppNavbar />

      <main className="max-w-3xl mx-auto px-4 py-8">
        {/* Navigation Breadcrumb */}
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={() => navigate('/tasks')}
            className="inline-flex items-center gap-2 text-sm text-surface-400 hover:text-surface-200 transition-colors"
          >
            ← Back to Daily Tasks
          </button>
          {taskId && (
            <Link
              to={`/evaluations/${taskId}`}
              className="text-sm text-primary-400 hover:underline"
            >
              View Code Evaluation →
            </Link>
          )}
        </div>

        {/* Loading State */}
        {loading && (
          <div className="p-12 text-center space-y-4 rounded-2xl bg-surface-900/40 border border-surface-800">
            <div className="w-10 h-10 mx-auto rounded-full border-2 border-primary-500 border-t-transparent animate-spin" />
            <p className="text-surface-400 text-sm">Checking interview eligibility...</p>
          </div>
        )}

        {/* Generic Network Error */}
        {!loading && error && (
          <div className="p-6 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-400 space-y-3">
            <h2 className="font-semibold text-base">Error Loading Interview</h2>
            <p className="text-sm text-red-300/80">{error}</p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-200 transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* 404: Session Not Ready */}
        {!loading && sessionNotFound && (
          <div className="p-8 rounded-2xl bg-surface-900/40 border border-surface-800 text-center space-y-4">
            <div className="w-14 h-14 mx-auto rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-2xl">
              ⏳
            </div>
            <h1 className="text-xl font-bold text-surface-50">Interview Not Ready Yet</h1>
            <p className="text-surface-300 text-sm max-w-md mx-auto">
              Your interview will be available once your submission is evaluated. If you recently
              submitted your solution, automated evaluation and mentor analysis are currently running.
            </p>
            <div className="pt-2 flex justify-center gap-3">
              {taskId && (
                <button
                  onClick={() => navigate(`/evaluations/${taskId}`)}
                  className="px-5 py-2.5 rounded-xl bg-surface-800 hover:bg-surface-700 text-sm font-medium transition-colors"
                >
                  Check Evaluation Status
                </button>
              )}
              <button
                onClick={() => navigate('/tasks')}
                className="px-5 py-2.5 rounded-xl bg-primary-600 hover:bg-primary-500 text-white text-sm font-medium transition-colors"
              >
                Return to Daily Tasks
              </button>
            </div>
          </div>
        )}

        {/* Active Session States */}
        {!loading && session && (
          <div className="space-y-6">
            {/* Header Badge & Title */}
            <div className="p-6 sm:p-8 rounded-2xl bg-surface-900/60 border border-surface-800 space-y-4 backdrop-blur-xl">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-primary-500/15 text-primary-300 border border-primary-500/25">
                  <span>🤖</span> Agent 4 AI Mock Interview
                </div>

                {/* Status Badges */}
                {session.status === 'AVAILABLE' && (
                  <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/25">
                    <span>⏱️</span> {formatRemainingTime(session.time_remaining_seconds)}
                  </div>
                )}
                {session.status === 'IN_PROGRESS' && (
                  <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-amber-500/15 text-amber-300 border border-amber-500/25">
                    <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                    In Progress
                  </div>
                )}
                {session.status === 'COMPLETED' && (
                  <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/25">
                    <span>✓</span> Completed
                  </div>
                )}
                {session.status === 'EXPIRED' && (
                  <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-surface-800 text-surface-400 border border-surface-700">
                    Window Expired
                  </div>
                )}
                {session.status === 'TERMINATED_VIOLATION' && (
                  <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-red-500/15 text-red-300 border border-red-500/25">
                    <span>⚠️</span> Terminated (Policy Violation)
                  </div>
                )}
              </div>

              <div>
                <h1 className="text-2xl sm:text-3xl font-bold text-surface-50 tracking-tight">
                  Technical System Defense Interview
                </h1>
                <p className="text-surface-300 text-sm mt-1">
                  Demonstrate your technical depth, explain architectural trade-offs, and defend your
                  implementation decisions in a realistic AI interviewer session.
                </p>
              </div>

              {/* State-specific Body Content */}

              {/* 1. AVAILABLE STATE */}
              {session.status === 'AVAILABLE' && (
                <div className="space-y-6 pt-2">
                  <div className="p-4 sm:p-5 rounded-xl bg-surface-950/70 border border-surface-800/80 space-y-3">
                    <h2 className="text-xs font-bold text-primary-400 uppercase tracking-wider">
                      What to expect & Rules
                    </h2>
                    <ul className="space-y-2.5 text-xs sm:text-sm text-surface-200">
                      <li className="flex items-start gap-2.5">
                        <span className="text-primary-400 font-bold mt-0.5">🖥️</span>
                        <div>
                          <strong className="text-surface-100">Fullscreen Focus:</strong> The interview runs
                          in focused mode to recreate realistic interview conditions.
                        </div>
                      </li>
                      <li className="flex items-start gap-2.5">
                        <span className="text-primary-400 font-bold mt-0.5">🎙️</span>
                        <div>
                          <strong className="text-surface-100">Voice & Text Answers:</strong> Speak or type
                          your responses to questions generated directly from your code evaluation findings.
                        </div>
                      </li>
                      <li className="flex items-start gap-2.5">
                        <span className="text-primary-400 font-bold mt-0.5">⏱️</span>
                        <div>
                          <strong className="text-surface-100">Continuous Assessment:</strong> Once started,
                          the session progresses turn by turn (approximately 6 questions) and cannot be paused.
                        </div>
                      </li>
                      <li className="flex items-start gap-2.5">
                        <span className="text-primary-400 font-bold mt-0.5">⚠️</span>
                        <div>
                          <strong className="text-surface-100">Integrity Proctoring:</strong> Tab switching,
                          window minimization, or exiting fullscreen are recorded. Repeated violations (3 warnings)
                          automatically terminate the interview.
                        </div>
                      </li>
                    </ul>
                  </div>

                  <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
                    <span className="text-xs text-surface-400">
                      Window expires in {formatRemainingTime(session.time_remaining_seconds)}
                    </span>
                    <button
                      id="start-interview-btn"
                      onClick={() => navigate(`/interview/${taskId}/room?mode=start`)}
                      className="w-full sm:w-auto px-8 py-3.5 rounded-xl bg-gradient-to-r from-primary-500 to-primary-600 hover:from-primary-400 hover:to-primary-500 text-white font-semibold text-sm transition-all shadow-lg shadow-primary-500/25 flex items-center justify-center gap-2"
                    >
                      <span>🚀</span> Start Interview
                    </button>
                  </div>
                </div>
              )}

              {/* 2. IN_PROGRESS STATE */}
              {session.status === 'IN_PROGRESS' && (
                <div className="space-y-5 pt-2">
                  <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-200 text-sm space-y-1">
                    <p className="font-semibold flex items-center gap-1.5">
                      <span>⚠️</span> Interview Already In Progress
                    </p>
                    <p className="text-xs text-amber-300/80">
                      You have an active session in progress. Your previous answers are preserved and you
                      can continue directly from your current question.
                    </p>
                    {session.violation_count > 0 && (
                      <p className="text-xs font-mono text-amber-400 pt-1">
                        Active warnings recorded: {session.violation_count} of 3
                      </p>
                    )}
                  </div>

                  <div className="flex justify-end pt-2">
                    <button
                      id="resume-interview-btn"
                      onClick={() => navigate(`/interview/${taskId}/room?mode=resume`)}
                      className="w-full sm:w-auto px-8 py-3.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-white font-semibold text-sm transition-all shadow-lg shadow-amber-500/25 flex items-center justify-center gap-2"
                    >
                      <span>▶️</span> Resume Interview
                    </button>
                  </div>
                </div>
              )}

              {/* 3. COMPLETED STATE */}
              {session.status === 'COMPLETED' && (
                <div className="space-y-5 pt-2">
                  <div className="p-5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 space-y-4">
                    <div className="flex items-center justify-between">
                      <h2 className="text-sm font-bold text-emerald-300 flex items-center gap-1.5">
                        <span>🎉</span> Interview Completed
                      </h2>
                      <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                        Defense Recorded
                      </span>
                    </div>

                    {session.overall_performance_summary?.summary && (
                      <p className="text-xs text-emerald-200/90 leading-relaxed">
                        {session.overall_performance_summary.summary}
                      </p>
                    )}

                    {/* Qualitative Defense Signals (Agent 4) */}
                    {session.overall_performance_summary && (
                      <div className="space-y-3 pt-2 border-t border-emerald-500/20">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-bold uppercase tracking-wider text-surface-400">
                            Interview Defense Signals (Agent 4)
                          </span>
                          <span className="text-[10px] text-surface-400 italic">
                            Individual defense indicators (not a unified score)
                          </span>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                          {/* Communication Clarity */}
                          <div className="p-3 rounded-lg bg-surface-950/70 border border-surface-800 space-y-2">
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-surface-300 font-medium flex items-center gap-1.5">
                                <span>💬</span> Communication
                              </span>
                              <span className="font-mono font-bold text-cyan-400">
                                {session.overall_performance_summary.communication_clarity}/100
                              </span>
                            </div>
                            <div className="w-full bg-surface-800 rounded-full h-1.5 overflow-hidden">
                              <div
                                className="h-1.5 rounded-full bg-cyan-400 transition-all duration-500"
                                style={{
                                  width: `${Math.min(100, Math.max(0, session.overall_performance_summary.communication_clarity))}%`,
                                }}
                              />
                            </div>
                            <p className="text-[10px] text-surface-400">Clarity & articulation</p>
                          </div>

                          {/* Technical Depth */}
                          <div className="p-3 rounded-lg bg-surface-950/70 border border-surface-800 space-y-2">
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-surface-300 font-medium flex items-center gap-1.5">
                                <span>⚙️</span> Technical Depth
                              </span>
                              <span className="font-mono font-bold text-emerald-400">
                                {session.overall_performance_summary.technical_depth}/100
                              </span>
                            </div>
                            <div className="w-full bg-surface-800 rounded-full h-1.5 overflow-hidden">
                              <div
                                className="h-1.5 rounded-full bg-emerald-400 transition-all duration-500"
                                style={{
                                  width: `${Math.min(100, Math.max(0, session.overall_performance_summary.technical_depth))}%`,
                                }}
                              />
                            </div>
                            <p className="text-[10px] text-surface-400">Architecture & trade-offs</p>
                          </div>

                          {/* Confidence Signals */}
                          <div className="p-3 rounded-lg bg-surface-950/70 border border-surface-800 space-y-2">
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-surface-300 font-medium flex items-center gap-1.5">
                                <span>🎯</span> Confidence
                              </span>
                              <span className="font-mono font-bold text-violet-400">
                                {session.overall_performance_summary.confidence_signals}/100
                              </span>
                            </div>
                            <div className="w-full bg-surface-800 rounded-full h-1.5 overflow-hidden">
                              <div
                                className="h-1.5 rounded-full bg-violet-400 transition-all duration-500"
                                style={{
                                  width: `${Math.min(100, Math.max(0, session.overall_performance_summary.confidence_signals))}%`,
                                }}
                              />
                            </div>
                            <p className="text-[10px] text-surface-400">Directness & composure</p>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Agent 5 notice */}
                  <div className="p-4 rounded-xl bg-gradient-to-r from-primary-950/40 via-surface-900 to-surface-950 border border-primary-500/30 flex items-start gap-3">
                    <span className="text-xl mt-0.5">⏳</span>
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <h3 className="text-xs font-bold text-primary-300 uppercase tracking-wider">
                          Final Combined Feedback Coming Soon
                        </h3>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-primary-500/20 text-primary-300 border border-primary-500/30">
                          Agent 5
                        </span>
                      </div>
                      <p className="text-xs text-surface-300 leading-relaxed">
                        Agent 5 will synthesize your code submission (Agent 3) and your technical defense interview (Agent 4) into a unified final assessment.
                      </p>
                    </div>
                  </div>

                  <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
                    <span className="text-xs text-surface-400">
                      Your technical defense has been saved and will be included in the milestone assessment.
                    </span>
                    <button
                      onClick={() => navigate('/tasks')}
                      className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-surface-800 hover:bg-surface-700 text-surface-200 text-sm font-medium transition-colors"
                    >
                      Back to Daily Tasks
                    </button>
                  </div>
                </div>
              )}

              {/* 4. EXPIRED STATE */}
              {session.status === 'EXPIRED' && (
                <div className="p-5 rounded-xl bg-surface-900 border border-surface-800 space-y-3">
                  <h2 className="text-sm font-bold text-surface-300">Session Window Expired</h2>
                  <p className="text-xs text-surface-400 leading-relaxed">
                    This interview window expired because it was not started within 24 hours of your code
                    evaluation. Don't worry — your completed task submission remains recorded. Keep advancing
                    through your roadmap to unlock future mock interviews.
                  </p>
                  <div className="pt-2">
                    <button
                      onClick={() => navigate('/history')}
                      className="px-5 py-2.5 rounded-xl bg-surface-800 hover:bg-surface-700 text-surface-200 text-xs font-semibold transition-colors"
                    >
                      View Task History →
                    </button>
                  </div>
                </div>
              )}

              {/* 5. TERMINATED_VIOLATION STATE */}
              {session.status === 'TERMINATED_VIOLATION' && (
                <div className="p-5 rounded-xl bg-red-500/10 border border-red-500/20 space-y-3">
                  <h2 className="text-sm font-bold text-red-300 flex items-center gap-1.5">
                    <span>🛑</span> Interview Terminated
                  </h2>
                  <p className="text-xs text-red-200/80 leading-relaxed">
                    {session.termination_reason ||
                      'The interview session was automatically terminated following repeated proctoring rule violations (e.g. exiting fullscreen mode or switching tabs).'}
                  </p>
                  <p className="text-xs text-surface-400">
                    Total violations recorded: {session.violation_count}. Answers submitted prior to termination
                    were saved.
                  </p>
                  <div className="pt-2">
                    <button
                      onClick={() => navigate('/tasks')}
                      className="px-5 py-2.5 rounded-xl bg-surface-800 hover:bg-surface-700 text-surface-200 text-xs font-semibold transition-colors"
                    >
                      Return to Tasks
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
