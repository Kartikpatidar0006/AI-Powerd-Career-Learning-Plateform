/**
 * DailyTaskPage — The core task flow page.
 *
 * Shows the user's current active task (ASSIGNED / IN_PROGRESS / SUBMITTED / EVALUATING)
 * or fetches the next task when no active task exists.
 *
 * Task lifecycle:
 * - ASSIGNED: Show task + "Start Working" button
 * - IN_PROGRESS: Show task + GitHub URL submission form
 * - SUBMITTED: Show submitted state + GitHub URL (re-submission allowed)
 * - EVALUATING: Show live evaluation progress panel with polling
 * - EVALUATED: Show full evaluation result (next task available)
 * - roadmap_completed: Show congratulations screen
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import AppNavbar from '../components/AppNavbar';
import {
  getCurrentTask,
  getNextTask,
  startTask,
  submitTask,
} from '../services/roadmap';
import type { Task, TaskStatus } from '../services/roadmap';
import { getEvaluationForTask } from '../services/evaluator';
import type { EvaluationResult, CheckResultResponse } from '../services/evaluator';

// ── Difficulty indicator ───────────────────────────────────────────

const DIFFICULTY_COLORS = ['', 'text-emerald-400', 'text-sky-400', 'text-amber-400', 'text-orange-400', 'text-red-400'];
const DIFFICULTY_LABELS = ['', 'Beginner', 'Intermediate', 'Advanced', 'Expert', 'Master'];

function DifficultyDots({ level }: { level: number }) {
  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((d) => (
        <div
          key={d}
          className={`w-2 h-2 rounded-full transition-all ${
            d <= level
              ? `opacity-100 ${DIFFICULTY_COLORS[level].replace('text-', 'bg-')}`
              : 'bg-surface-700 opacity-40'
          }`}
        />
      ))}
      <span className={`ml-1.5 text-xs font-medium ${DIFFICULTY_COLORS[level] || 'text-surface-400'}`}>
        {DIFFICULTY_LABELS[level]}
      </span>
    </div>
  );
}

// ── Status badge ───────────────────────────────────────────────────

function StatusBadge({ status }: { status: TaskStatus }) {
  const configs: Record<string, { label: string; className: string }> = {
    ASSIGNED: { label: 'Assigned', className: 'bg-sky-500/15 text-sky-400 border-sky-500/30' },
    IN_PROGRESS: { label: 'In Progress', className: 'bg-amber-500/15 text-amber-400 border-amber-500/30' },
    SUBMITTED: { label: 'Under Review', className: 'bg-violet-500/15 text-violet-400 border-violet-500/30' },
    EVALUATING: { label: 'Evaluating…', className: 'bg-orange-500/15 text-orange-400 border-orange-500/30' },
    EVALUATED: { label: 'Evaluated', className: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' },
  };
  const config = configs[status] ?? { label: status, className: 'bg-surface-800 text-surface-400 border-surface-700' };
  return (
    <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold border ${config.className}`}>
      {config.label}
    </span>
  );
}

// ── GitHub URL form ────────────────────────────────────────────────

function GitHubSubmitForm({
  taskId,
  currentUrl,
  onSubmitted,
}: {
  taskId: string;
  currentUrl: string | null;
  onSubmitted: (task: Task) => void;
}) {
  const [url, setUrl] = useState(currentUrl || '');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) {
      setError('GitHub repository URL is required');
      return;
    }
    if (!url.startsWith('https://github.com/')) {
      setError('URL must start with https://github.com/');
      return;
    }
    try {
      setSubmitting(true);
      setError(null);
      const updated = await submitTask(taskId, url.trim());
      onSubmitted(updated);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail: string } } })?.response?.data?.detail;
      setError(detail || 'Failed to submit. Please check the URL and try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label htmlFor="github-url" className="block text-sm font-semibold text-surface-300 mb-1.5">
          GitHub Repository URL
        </label>
        <div className="flex gap-2">
          <input
            id="github-url"
            type="url"
            value={url}
            onChange={(e) => { setUrl(e.target.value); setError(null); }}
            placeholder="https://github.com/username/repo-name"
            className={`flex-1 px-4 py-2.5 rounded-xl bg-surface-800/80 border text-sm text-surface-100 placeholder-surface-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 transition-all ${
              error ? 'border-danger-500/60' : 'border-surface-700/60 hover:border-surface-600'
            }`}
          />
          <button
            type="submit"
            id="submit-task-btn"
            disabled={submitting}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-primary-500 to-primary-600 text-white font-semibold text-sm hover:from-primary-400 hover:to-primary-500 transition-all disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap shadow-md shadow-primary-500/20"
          >
            {submitting ? '…' : currentUrl ? 'Update URL' : 'Submit Task'}
          </button>
        </div>
        {error && <p className="mt-1.5 text-xs text-danger-400">{error}</p>}
      </div>
    </form>
  );
}

// ── Evaluation result panel ────────────────────────────────────────

function ScoreRing({ score, passed }: { score: number; passed: boolean }) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = passed ? '#10b981' : score >= 40 ? '#f59e0b' : '#ef4444';
  return (
    <div className="relative w-28 h-28 flex-shrink-0">
      <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
        <circle cx="50" cy="50" r={radius} fill="none" stroke="#1e293b" strokeWidth="10" />
        <circle
          cx="50" cy="50" r={radius} fill="none"
          stroke={color} strokeWidth="10"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 1s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold" style={{ color }}>{Math.round(score)}</span>
        <span className="text-xs text-surface-400">/ 100</span>
      </div>
    </div>
  );
}

function EvaluationPanel({ evaluation }: { evaluation: EvaluationResult }) {
  const navigate = useNavigate();
  const { final_score, passed, feedback_summary, deterministic_checks, llm_strengths, llm_weaknesses, llm_suggestions } = evaluation;

  const isCompleted = evaluation.status === 'COMPLETED';
  const isFailed = evaluation.status === 'FAILED';

  return (
    <div className={`p-5 rounded-2xl border space-y-5 ${
      isCompleted && passed ? 'bg-emerald-500/5 border-emerald-500/20'
      : isCompleted && !passed ? 'bg-red-500/5 border-red-500/20'
      : 'bg-orange-500/5 border-orange-500/20'
    }`}>
      {/* Header */}
      <div className="flex items-center gap-4">
        {isCompleted && final_score !== null && (
          <ScoreRing score={final_score} passed={!!passed} />
        )}
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-lg">{isCompleted && passed ? '🎉' : isFailed ? '⚠️' : '📝'}</span>
            <h3 className={`text-base font-bold ${
              isCompleted && passed ? 'text-emerald-400'
              : isFailed ? 'text-orange-400'
              : 'text-red-400'
            }`}>
              {isCompleted && passed ? 'Task Passed!' : isFailed ? 'Evaluation Failed' : 'Needs Improvement'}
            </h3>
          </div>
          {feedback_summary && (
            <p className="text-sm text-surface-300 leading-relaxed">{feedback_summary}</p>
          )}
          {isFailed && evaluation.error_detail && (
            <p className="text-sm text-orange-300 mt-1">{evaluation.error_detail}</p>
          )}
        </div>
      </div>

      {/* Deterministic checks breakdown */}
      {deterministic_checks && deterministic_checks.length > 0 && (
        <div>
          <h4 className="text-xs font-bold text-surface-400 uppercase tracking-widest mb-3">Code Review Checks</h4>
          <div className="space-y-2">
            {deterministic_checks.map((c: CheckResultResponse, i: number) => (
              <div key={i} className={`flex items-start gap-3 p-3 rounded-xl text-sm ${
                c.passed ? 'bg-emerald-500/8 border border-emerald-500/15' : 'bg-red-500/8 border border-red-500/15'
              }`}>
                <span className={`text-base flex-shrink-0 ${c.passed ? 'text-emerald-400' : 'text-red-400'}`}>
                  {c.passed ? '✓' : '✗'}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className={`font-semibold ${c.passed ? 'text-emerald-300' : 'text-red-300'}`}>
                      {c.check_name.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                    </span>
                    <span className={`text-xs font-mono flex-shrink-0 ${c.passed ? 'text-emerald-400' : 'text-surface-500'}`}>
                      {c.score_contribution.toFixed(1)}/{c.weight_pct.toFixed(0)} pts
                    </span>
                  </div>
                  <p className="text-xs text-surface-400 mt-0.5 leading-relaxed">{c.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* LLM insights */}
      {(llm_strengths?.length || llm_weaknesses?.length || llm_suggestions?.length) && (
        <div className="grid gap-4 md:grid-cols-3">
          {llm_strengths && llm_strengths.length > 0 && (
            <div>
              <h4 className="text-xs font-bold text-emerald-400 uppercase tracking-widest mb-2">💪 Strengths</h4>
              <ul className="space-y-1">
                {llm_strengths.slice(0,3).map((s, i) => (
                  <li key={i} className="text-xs text-surface-300 flex items-start gap-1.5">
                    <span className="text-emerald-400 flex-shrink-0">•</span>{s}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {llm_weaknesses && llm_weaknesses.length > 0 && (
            <div>
              <h4 className="text-xs font-bold text-amber-400 uppercase tracking-widest mb-2">⚠️ Weaknesses</h4>
              <ul className="space-y-1">
                {llm_weaknesses.slice(0,3).map((w, i) => (
                  <li key={i} className="text-xs text-surface-300 flex items-start gap-1.5">
                    <span className="text-amber-400 flex-shrink-0">•</span>{w}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {llm_suggestions && llm_suggestions.length > 0 && (
            <div>
              <h4 className="text-xs font-bold text-sky-400 uppercase tracking-widest mb-2">💡 Suggestions</h4>
              <ul className="space-y-1">
                {llm_suggestions.slice(0, 3).map((s, i) => (
                  <li key={i} className="text-xs text-surface-300 flex items-start gap-1.5">
                    <span className="text-sky-400 flex-shrink-0">•</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Link to full dedicated report */}
      {isCompleted && (
        <div className="pt-2 flex justify-end">
          <button
            onClick={() => navigate(`/evaluations/${evaluation.task_id}`)}
            className="text-xs font-semibold text-primary-400 hover:text-primary-300 flex items-center gap-1 transition-colors"
          >
            View Full Evaluation Report & Feedback Breakdown →
          </button>
        </div>
      )}
    </div>
  );
}

// ── Evaluating status panel ────────────────────────────────────────

function EvaluatingPanel() {
  return (
    <div className="p-5 rounded-2xl bg-orange-500/5 border border-orange-500/20 flex items-center gap-4">
      <div className="w-10 h-10 flex-shrink-0">
        <svg className="w-full h-full animate-spin text-orange-400" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
      </div>
      <div>
        <p className="text-sm font-bold text-orange-300">Evaluating Your Repository…</p>
        <p className="text-xs text-surface-400 mt-0.5">
          Agent 3 is analysing your code. This usually takes 20–60 seconds.
          The result will appear here automatically.
        </p>
      </div>
    </div>
  );
}

// ── Task card ──────────────────────────────────────────────────────

function TaskCard({
  task,
  onTaskUpdate,
}: {
  task: Task;
  onTaskUpdate: (t: Task) => void;
}) {
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationResult | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Poll for evaluation when task is EVALUATING
  useEffect(() => {
    const isEvaluating = task.status === 'EVALUATING' || task.status === 'SUBMITTED';
    if (!isEvaluating) {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }
    const poll = async () => {
      try {
        const result = await getEvaluationForTask(task.id);
        if (result) {
          setEvaluation(result);
          if (result.status === 'COMPLETED' || result.status === 'FAILED') {
            if (pollRef.current) clearInterval(pollRef.current);
          }
        }
      } catch {
        // Silently ignore poll errors
      }
    };
    poll(); // Immediate first call
    pollRef.current = setInterval(poll, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [task.id, task.status]);

  const handleStart = async () => {
    try {
      setStarting(true);
      setError(null);
      const updated = await startTask(task.id);
      onTaskUpdate(updated);
    } catch {
      setError('Failed to start task. Please try again.');
    } finally {
      setStarting(false);
    }
  };

  const evalSummary = task.evaluation_summary as
    | { score?: number; feedback?: string; passed?: boolean }
    | null;

  return (
    <div className="space-y-6">
      {/* Task header */}
      <div className="p-6 rounded-2xl bg-surface-900/80 border border-surface-800/50 shadow-lg">
        <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs text-surface-500 font-mono">Task #{task.sequence_number}</span>
              <span className="text-xs text-surface-600">·</span>
              <span className="text-xs text-surface-500">Milestone {task.milestone_order}</span>
            </div>
            <h2 className="text-xl font-bold text-surface-100">{task.title}</h2>
          </div>
          <StatusBadge status={task.status as TaskStatus} />
        </div>

        <div className="flex flex-wrap gap-4 text-sm text-surface-400 mb-4">
          <div className="flex items-center gap-1.5">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {task.estimated_hours}h estimated
          </div>
          <DifficultyDots level={task.difficulty} />
        </div>

        <p className="text-surface-300 text-sm leading-relaxed">{task.description}</p>
      </div>

      {/* Requirements */}
      <div className="p-5 rounded-2xl bg-surface-950/60 border border-surface-800/30">
        <h3 className="text-sm font-bold text-surface-200 mb-3 flex items-center gap-2">
          <span className="w-5 h-5 rounded bg-primary-500/15 flex items-center justify-center">
            <svg className="w-3 h-3 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
          </span>
          Requirements
        </h3>
        <ul className="space-y-2">
          {task.requirements.map((req, i) => (
            <li key={i} className="text-sm text-surface-300 flex items-start gap-2">
              <span className="text-primary-400 font-mono text-xs mt-0.5 w-4 flex-shrink-0">{i + 1}.</span>
              {req.replace(/^\d+\.\s*/, '')}
            </li>
          ))}
        </ul>
      </div>

      {/* Acceptance criteria */}
      <div className="p-5 rounded-2xl bg-surface-950/60 border border-surface-800/30">
        <h3 className="text-sm font-bold text-surface-200 mb-3 flex items-center gap-2">
          <span className="w-5 h-5 rounded bg-accent-500/15 flex items-center justify-center">
            <svg className="w-3 h-3 text-accent-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </span>
          Acceptance Criteria
        </h3>
        <ul className="space-y-2">
          {task.acceptance_criteria.map((criterion, i) => (
            <li key={i} className="text-sm text-surface-300 flex items-start gap-2">
              <svg className="w-4 h-4 text-accent-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              {criterion}
            </li>
          ))}
        </ul>
      </div>

      {/* Skills */}
      {task.skills_targeted.length > 0 && (
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-xs text-surface-500 font-semibold uppercase tracking-widest">Skills:</span>
          {task.skills_targeted.map((skill) => (
            <span
              key={skill}
              className="px-2.5 py-0.5 text-xs rounded-full bg-primary-500/10 text-primary-300 border border-primary-500/20 font-medium"
            >
              {skill}
            </span>
          ))}
        </div>
      )}

      {/* Starter hint */}
      {task.starter_hint && (
        <div className="p-4 rounded-xl bg-amber-500/8 border border-amber-500/20">
          <p className="text-xs font-bold text-amber-400 uppercase tracking-widest mb-1">💡 Starter Hint</p>
          <p className="text-sm text-amber-200/80">{task.starter_hint}</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="p-3 rounded-xl bg-danger-500/10 border border-danger-500/20 text-danger-400 text-sm">
          {error}
        </div>
      )}

      {/* Action area */}
      {task.status === 'ASSIGNED' && (
        <button
          id="start-task-btn"
          onClick={handleStart}
          disabled={starting}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-primary-500 to-primary-600 text-white font-semibold hover:from-primary-400 hover:to-primary-500 transition-all shadow-lg shadow-primary-500/25 hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {starting ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
              Starting…
            </span>
          ) : (
            '▶ Start Working on This Task'
          )}
        </button>
      )}

      {(task.status === 'IN_PROGRESS' || task.status === 'SUBMITTED') && (
        <div className="p-5 rounded-2xl bg-surface-900/80 border border-surface-800/40 space-y-3">
          <h3 className="text-sm font-bold text-surface-200">
            {task.status === 'SUBMITTED' ? '🔄 Update Submission' : '📤 Submit Your Work'}
          </h3>
          <p className="text-xs text-surface-400">
            Push your code to GitHub and paste the repository URL below.
            {task.status === 'SUBMITTED' && ' You can update the URL before evaluation.'}
          </p>
          {task.github_repo_url && task.status === 'SUBMITTED' && (
            <div className="text-xs text-surface-400">
              Current submission:{' '}
              <a
                href={task.github_repo_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary-400 hover:underline"
              >
                {task.github_repo_url}
              </a>
            </div>
          )}
          <GitHubSubmitForm
            taskId={task.id}
            currentUrl={task.github_repo_url}
            onSubmitted={onTaskUpdate}
          />
        </div>
      )}

      {/* EVALUATING: show live poll panel */}
      {(task.status === 'EVALUATING' || task.status === 'SUBMITTED') && !evaluation && (
        <EvaluatingPanel />
      )}

      {/* Show live evaluation result from Agent 3 */}
      {evaluation && (evaluation.status === 'COMPLETED' || evaluation.status === 'FAILED') && (
        <EvaluationPanel evaluation={evaluation} />
      )}

      {/* Evaluated result from task summary (fallback when no live eval) */}
      {task.status === 'EVALUATED' && evalSummary && !evaluation && (
        <div className={`p-5 rounded-2xl border ${evalSummary.passed ? 'bg-emerald-500/8 border-emerald-500/20' : 'bg-danger-500/8 border-danger-500/20'}`}>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-lg">{evalSummary.passed ? '🎉' : '📝'}</span>
            <h3 className={`text-sm font-bold ${evalSummary.passed ? 'text-emerald-400' : 'text-danger-400'}`}>
              {evalSummary.passed ? 'Task Passed!' : 'Keep Improving'}
            </h3>
            {evalSummary.score !== undefined && (
              <span className={`ml-auto font-mono text-sm font-bold ${evalSummary.passed ? 'text-emerald-400' : 'text-danger-400'}`}>
                {evalSummary.score}/100
              </span>
            )}
          </div>
          {evalSummary.feedback && (
            <p className="text-sm text-surface-300">{evalSummary.feedback}</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────

export default function DailyTaskPage() {
  const navigate = useNavigate();
  const [task, setTask] = useState<Task | null>(null);
  const [roadmapCompleted, setRoadmapCompleted] = useState(false);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadCurrentTask = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const current = await getCurrentTask();
      setTask(current);
    } catch {
      setError('Failed to load your current task.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCurrentTask();
  }, [loadCurrentTask]);

  const handleGetNextTask = async () => {
    try {
      setFetching(true);
      setError(null);
      const result = await getNextTask();
      if (result.status === 'roadmap_completed') {
        setRoadmapCompleted(true);
        setTask(null);
      } else {
        setTask(result.task);
      }
    } catch (err: unknown) {
      const status = (err as { response?: { status: number } })?.response?.status;
      if (status === 409) {
        const detail = (err as { response?: { data?: { detail: string } } })?.response?.data?.detail || '';
        if (detail.includes('Generate') || detail.includes('roadmap')) {
          setError('Please generate your roadmap first.');
        } else {
          // Reload active task
          await loadCurrentTask();
        }
      } else if (status === 504) {
        setError('AI timed out generating your task. Please try again.');
      } else {
        setError('Failed to get next task. Please try again.');
      }
    } finally {
      setFetching(false);
    }
  };

  // ── Completed state ─────────────────────────────────────────────
  if (roadmapCompleted) {
    return (
      <div className="min-h-screen">
        <AppNavbar />
        <div className="max-w-2xl mx-auto px-4 py-16 text-center">
          <div className="w-24 h-24 mx-auto mb-6 rounded-full bg-gradient-to-br from-emerald-500/20 to-accent-500/20 border border-emerald-500/30 flex items-center justify-center text-4xl">
            🎓
          </div>
          <h1 className="text-3xl font-bold text-surface-100 mb-3">Roadmap Complete!</h1>
          <p className="text-surface-400 text-lg mb-8">
            You've completed all milestones in your learning roadmap. Outstanding work!
          </p>
          <button
            onClick={() => navigate('/roadmap')}
            className="px-8 py-3 rounded-xl bg-gradient-to-r from-primary-500 to-primary-600 text-white font-semibold hover:from-primary-400 hover:to-primary-500 transition-all shadow-lg"
          >
            View Your Completed Roadmap
          </button>
        </div>
      </div>
    );
  }

  // ── Loading skeleton ─────────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen">
        <AppNavbar />
        <div className="max-w-2xl mx-auto px-4 py-8 space-y-6 animate-pulse">
          <div className="h-8 bg-surface-800 rounded-xl w-56" />
          <div className="h-48 bg-surface-900 rounded-2xl border border-surface-800" />
          <div className="h-32 bg-surface-900 rounded-2xl border border-surface-800" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <AppNavbar />
      <div className="max-w-2xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-surface-100">Daily Task</h1>
            <p className="text-surface-400 text-sm mt-1">Completion-based learning</p>
          </div>
          <button
            onClick={() => navigate('/history')}
            className="text-sm text-primary-400 hover:text-primary-300 transition-colors"
          >
            Task History →
          </button>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-xl bg-danger-500/10 border border-danger-500/20 text-danger-400 text-sm">
            {error}
          </div>
        )}

        {/* No current task — get next */}
        {!task ? (
          <div className="text-center py-12 px-4">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-primary-500/10 border border-primary-500/20 flex items-center justify-center text-2xl">
              ⚡
            </div>
            <h2 className="text-xl font-semibold text-surface-100 mb-2">Ready for Your Next Task?</h2>
            <p className="text-surface-400 text-sm mb-8">
              Complete the previous task first, or get your first task to start learning.
            </p>
            <button
              id="get-next-task-btn"
              onClick={handleGetNextTask}
              disabled={fetching}
              className="px-8 py-3 rounded-xl bg-gradient-to-r from-primary-500 to-primary-600 text-white font-semibold hover:from-primary-400 hover:to-primary-500 transition-all disabled:opacity-50 shadow-lg shadow-primary-500/25"
            >
              {fetching ? (
                <span className="flex items-center gap-2">
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  Generating task…
                </span>
              ) : (
                '✨ Get Next Task'
              )}
            </button>
          </div>
        ) : (
          <TaskCard task={task} onTaskUpdate={setTask} />
        )}
      </div>
    </div>
  );
}
