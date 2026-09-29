/**
 * TaskHistoryPage — Paginated view of all tasks with status filters.
 */

import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import AppNavbar from '../components/AppNavbar';
import { getTaskHistory } from '../services/roadmap';
import type { Task, TaskStatus } from '../services/roadmap';

const STATUS_COLORS: Record<string, string> = {
  ASSIGNED: 'text-sky-400 bg-sky-500/10 border-sky-500/20',
  IN_PROGRESS: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  SUBMITTED: 'text-violet-400 bg-violet-500/10 border-violet-500/20',
  EVALUATED: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
};

const STATUS_LABELS: Record<string, string> = {
  ASSIGNED: 'Assigned',
  IN_PROGRESS: 'In Progress',
  SUBMITTED: 'Submitted',
  EVALUATED: 'Evaluated',
};

const DIFFICULTY_LABELS = ['', 'Beginner', 'Intermediate', 'Advanced', 'Expert', 'Master'];
const DIFFICULTY_COLORS = ['', 'text-emerald-400', 'text-sky-400', 'text-amber-400', 'text-orange-400', 'text-red-400'];

function TaskRow({ task }: { task: Task }) {
  const navigate = useNavigate();
  const createdDate = new Date(task.created_at).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });

  return (
    <div
      className="p-4 rounded-xl bg-surface-900/60 border border-surface-800/40 hover:border-surface-700/60 hover:bg-surface-900/80 transition-all duration-150 cursor-pointer group"
      onClick={() => navigate('/tasks')}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && navigate('/tasks')}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono text-surface-500">#{task.sequence_number}</span>
            <span className="text-xs text-surface-600">·</span>
            <span className="text-xs text-surface-500">M{task.milestone_order}</span>
          </div>
          <h3 className="text-sm font-semibold text-surface-200 group-hover:text-surface-100 transition-colors truncate">
            {task.title}
          </h3>
          <div className="flex flex-wrap items-center gap-3 mt-1.5">
            <span className={`text-xs font-medium ${DIFFICULTY_COLORS[task.difficulty] || 'text-surface-400'}`}>
              {DIFFICULTY_LABELS[task.difficulty]} (D{task.difficulty})
            </span>
            <span className="text-xs text-surface-500">{task.estimated_hours}h</span>
            <span className="text-xs text-surface-600">{createdDate}</span>
          </div>
          {task.skills_targeted.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {task.skills_targeted.slice(0, 3).map((skill) => (
                <span
                  key={skill}
                  className="px-2 py-0.5 text-xs rounded-full bg-surface-800 text-surface-400 border border-surface-700/40"
                >
                  {skill}
                </span>
              ))}
              {task.skills_targeted.length > 3 && (
                <span className="px-2 py-0.5 text-xs rounded-full bg-surface-800 text-surface-500">
                  +{task.skills_targeted.length - 3}
                </span>
              )}
            </div>
          )}
        </div>

        <div className="flex flex-col items-end gap-2 flex-shrink-0">
          <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${STATUS_COLORS[task.status] || ''}`}>
            {STATUS_LABELS[task.status] || task.status}
          </span>
          {task.status === 'EVALUATED' && task.evaluation_summary && (
            <span className="text-xs font-mono text-emerald-400">
              {(task.evaluation_summary as { score?: number }).score ?? '—'}/100
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export default function TaskHistoryPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<TaskStatus | 'ALL'>('ALL');
  const PAGE_SIZE = 15;

  const loadTasks = useCallback(async (p = 1) => {
    try {
      setLoading(true);
      setError(null);
      const result = await getTaskHistory(p, PAGE_SIZE);
      setTasks(result.tasks);
      setTotal(result.total);
      setPage(p);
    } catch {
      setError('Failed to load task history. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTasks(1);
  }, [loadTasks]);

  const filtered = filter === 'ALL' ? tasks : tasks.filter((t) => t.status === filter);
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="min-h-screen">
      <AppNavbar />
      <div className="max-w-2xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-surface-100">Task History</h1>
          <p className="text-surface-400 text-sm mt-1">{total} tasks total</p>
        </div>

        {/* Status filters */}
        <div className="flex flex-wrap gap-2 mb-6">
          {(['ALL', 'ASSIGNED', 'IN_PROGRESS', 'SUBMITTED', 'EVALUATED'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                filter === s
                  ? 'bg-primary-500/20 text-primary-300 border border-primary-500/30'
                  : 'bg-surface-800/60 text-surface-400 border border-surface-700/30 hover:border-surface-600'
              }`}
            >
              {s === 'ALL' ? 'All' : STATUS_LABELS[s]}
            </button>
          ))}
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 p-3 rounded-xl bg-danger-500/10 border border-danger-500/20 text-danger-400 text-sm">
            {error}
          </div>
        )}

        {/* Tasks */}
        {loading ? (
          <div className="space-y-3 animate-pulse">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-20 bg-surface-900 rounded-xl border border-surface-800" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12 text-surface-500">
            <p className="text-lg mb-1">No tasks found</p>
            <p className="text-sm">
              {filter !== 'ALL' ? 'Try a different filter' : 'Complete your onboarding and generate a roadmap to get started'}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((task) => (
              <TaskRow key={task.id} task={task} />
            ))}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex justify-center gap-3 mt-8">
            <button
              onClick={() => loadTasks(page - 1)}
              disabled={page === 1}
              className="px-4 py-2 rounded-lg bg-surface-800 text-surface-300 text-sm font-medium disabled:opacity-40 hover:bg-surface-700 transition-all"
            >
              ← Previous
            </button>
            <span className="px-4 py-2 text-sm text-surface-400">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => loadTasks(page + 1)}
              disabled={page === totalPages}
              className="px-4 py-2 rounded-lg bg-surface-800 text-surface-300 text-sm font-medium disabled:opacity-40 hover:bg-surface-700 transition-all"
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
