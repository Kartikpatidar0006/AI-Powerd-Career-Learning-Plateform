/**
 * RoadmapPage — Displays the user's AI-generated learning roadmap
 * with milestone progress, skill targets, and difficulty indicators.
 *
 * Handles:
 * - First-time generation (no roadmap yet)
 * - Loading state with skeleton
 * - Already generated — display with progress
 * - Error states with actionable messages
 */

import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import AppNavbar from '../components/AppNavbar';
import {
  generateRoadmap,
  getMyRoadmap,
} from '../services/roadmap';
import type {
  Roadmap,
  MilestoneProgress,
} from '../services/roadmap';

// ── Difficulty badge ───────────────────────────────────────────────

const DIFFICULTY_COLORS = [
  '', // 0-indexed padding
  'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', // 1
  'bg-sky-500/20 text-sky-400 border-sky-500/30',            // 2
  'bg-amber-500/20 text-amber-400 border-amber-500/30',      // 3
  'bg-orange-500/20 text-orange-400 border-orange-500/30',   // 4
  'bg-red-500/20 text-red-400 border-red-500/30',            // 5
];

const DIFFICULTY_LABELS = ['', 'Beginner', 'Intermediate', 'Advanced', 'Expert', 'Master'];
const DIFFICULTY_DOTS = ['', '●', '●●', '●●●', '●●●●', '●●●●●'];

function DifficultyBadge({ level }: { level: number }) {
  const clampedLevel = Math.max(1, Math.min(5, level));
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-semibold rounded-full border ${DIFFICULTY_COLORS[clampedLevel]}`}
      title={`Difficulty: ${DIFFICULTY_LABELS[clampedLevel]}`}
    >
      <span className="tracking-widest text-xs opacity-60">{DIFFICULTY_DOTS[clampedLevel]}</span>
      {DIFFICULTY_LABELS[clampedLevel]}
    </span>
  );
}

// ── State badge ────────────────────────────────────────────────────

function MilestoneStateBadge({ state }: { state: MilestoneProgress['state'] }) {
  if (state === 'completed') {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
        <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
        </svg>
        Completed
      </span>
    );
  }
  if (state === 'current') {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-violet-500/20 text-violet-300 border border-violet-500/30 animate-pulse">
        <span className="w-2 h-2 rounded-full bg-violet-400 inline-block"></span>
        In Progress
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-surface-800/60 text-surface-400 border border-surface-700/40">
      <span className="w-2 h-2 rounded-full bg-surface-500 inline-block"></span>
      Upcoming
    </span>
  );
}

// ── Skill chip ─────────────────────────────────────────────────────

function SkillChip({ skill }: { skill: string }) {
  return (
    <span className="inline-block px-2.5 py-0.5 text-xs rounded-full bg-primary-500/10 text-primary-300 border border-primary-500/20 font-medium">
      {skill}
    </span>
  );
}

// ── Progress bar ──────────────────────────────────────────────────

function ProgressBar({ completed, planned }: { completed: number; planned: number }) {
  const pct = planned > 0 ? Math.round((completed / planned) * 100) : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-surface-800 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-primary-500 to-accent-500 transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-surface-400 font-mono w-10 text-right">
        {completed}/{planned}
      </span>
    </div>
  );
}

// ── Milestone card ────────────────────────────────────────────────

function MilestoneCard({ milestone, index }: { milestone: MilestoneProgress; index: number }) {
  const [expanded, setExpanded] = useState(milestone.state === 'current');

  return (
    <div
      className={`relative rounded-2xl border transition-all duration-300 ${
        milestone.state === 'current'
          ? 'border-violet-500/40 bg-surface-900/80 shadow-lg shadow-violet-500/10'
          : milestone.state === 'completed'
          ? 'border-emerald-500/20 bg-surface-950/60'
          : 'border-surface-800/40 bg-surface-950/40 opacity-75'
      }`}
    >
      {/* Connector line */}
      {index > 0 && (
        <div className="absolute -top-6 left-8 w-0.5 h-6 bg-gradient-to-b from-surface-800 to-transparent" />
      )}

      {/* Header */}
      <button
        className="w-full p-5 flex items-start gap-4 text-left group"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        {/* Order badge */}
        <div
          className={`flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm font-mono border ${
            milestone.state === 'completed'
              ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400'
              : milestone.state === 'current'
              ? 'bg-violet-500/25 border-violet-500/50 text-violet-300'
              : 'bg-surface-800/60 border-surface-700/40 text-surface-400'
          }`}
        >
          {milestone.state === 'completed' ? (
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
          ) : (
            milestone.order
          )}
        </div>

        {/* Title row */}
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-start gap-2 mb-1">
            <h3 className="text-base font-semibold text-surface-100 truncate">
              {milestone.title}
            </h3>
            <MilestoneStateBadge state={milestone.state} />
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm text-surface-400">
            <span>{milestone.estimated_days} days estimated</span>
            <DifficultyBadge level={milestone.difficulty_band} />
          </div>
          {/* Progress bar always visible */}
          <div className="mt-2 w-64">
            <ProgressBar completed={milestone.tasks_completed} planned={milestone.tasks_planned} />
          </div>
        </div>

        {/* Expand icon */}
        <svg
          className={`flex-shrink-0 w-5 h-5 text-surface-400 mt-0.5 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-5 pb-5 ml-14 border-t border-surface-800/40 pt-4 space-y-4 animate-in slide-in-from-top-2 duration-200">
          <p className="text-sm text-surface-300 leading-relaxed">{milestone.description}</p>

          {/* Skills */}
          {milestone.target_skills.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-surface-400 uppercase tracking-widest mb-2">Skills</p>
              <div className="flex flex-wrap gap-1.5">
                {milestone.target_skills.map((skill) => (
                  <SkillChip key={skill} skill={skill} />
                ))}
              </div>
            </div>
          )}

          {/* Success criteria */}
          {milestone.success_criteria.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-surface-400 uppercase tracking-widest mb-2">Success Criteria</p>
              <ul className="space-y-1.5">
                {milestone.success_criteria.map((criterion, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-surface-300">
                    <svg className="w-4 h-4 text-primary-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {criterion}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────

export default function RoadmapPage() {
  const navigate = useNavigate();
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRoadmap = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getMyRoadmap();
      setRoadmap(data);
    } catch (err: unknown) {
      const res = (err as { response?: { status?: number; data?: { detail?: string } } })?.response;
      const status = res?.status;
      if (status === 404) {
        // No roadmap yet — show generate prompt
        setRoadmap(null);
      } else if (status === 409 && res?.data?.detail?.toLowerCase().includes('onboarding')) {
        setError('Please complete your onboarding profile first.');
        setTimeout(() => navigate('/onboarding'), 1500);
      } else {
        setError('Failed to load your roadmap. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    fetchRoadmap();
  }, [fetchRoadmap]);

  const handleGenerate = async () => {
    try {
      setGenerating(true);
      setError(null);
      const data = await generateRoadmap();
      setRoadmap(data);
    } catch (err: unknown) {
      const res = (err as { response?: { status?: number; data?: { detail?: string } } })?.response;
      const status = res?.status;
      const detail = res?.data?.detail || '';
      if (status === 409) {
        if (detail.toLowerCase().includes('onboarding')) {
          setError('Please complete onboarding first before generating your roadmap.');
          setTimeout(() => navigate('/onboarding'), 1500);
        } else {
          // Already exists — fetch instead
          await fetchRoadmap();
        }
      } else if (status === 503) {
        setError('Profile service is currently unavailable. Please try again in a moment.');
      } else if (status === 504) {
        setError('AI Agent timed out. Please try again in a moment.');
      } else if (status === 502) {
        setError('AI produced an invalid plan. Please try again.');
      } else {
        setError(detail || 'Failed to generate roadmap. Please try again.');
      }
    } finally {
      setGenerating(false);
    }
  };

  // ── Computed stats ─────────────────────────────────────────────
  const totalCompleted = roadmap?.milestones.filter((m) => m.state === 'completed').length ?? 0;
  const totalMilestones = roadmap?.milestones.length ?? 0;
  const totalDays = roadmap?.milestones.reduce((sum, m) => sum + m.estimated_days, 0) ?? 0;
  const totalTasksCompleted = roadmap?.milestones.reduce((sum, m) => sum + m.tasks_completed, 0) ?? 0;
  const totalTasksPlanned = roadmap?.milestones.reduce((sum, m) => sum + m.tasks_planned, 0) ?? 0;
  const overallPct = totalMilestones > 0 ? Math.round((totalCompleted / totalMilestones) * 100) : 0;

  // ── Loading skeleton ────────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen">
        <AppNavbar />
        <div className="max-w-3xl mx-auto px-4 py-12 space-y-6 animate-pulse">
          <div className="h-8 bg-surface-800 rounded-xl w-64" />
          <div className="h-4 bg-surface-800 rounded w-96" />
          <div className="space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-24 bg-surface-900 rounded-2xl border border-surface-800" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  // ── No roadmap state ────────────────────────────────────────────
  if (!roadmap && !loading) {
    return (
      <div className="min-h-screen">
        <AppNavbar />
        <div className="max-w-2xl mx-auto px-4 py-16 text-center">
          {/* Animated icon */}
          <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-primary-500/20 to-accent-500/20 border border-primary-500/20 flex items-center justify-center">
            <svg className="w-10 h-10 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 6.75V15m6-6v8.25m.503 3.498l4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 00-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0z" />
            </svg>
          </div>

          <h1 className="text-3xl font-bold text-surface-100 mb-3">Your Learning Roadmap</h1>
          <p className="text-surface-400 text-lg mb-2">
            AI-powered, personalized to your profile and target role.
          </p>
          <p className="text-surface-500 text-sm mb-8 leading-relaxed max-w-md mx-auto">
            Our AI will analyze your skills, experience, and career goal to generate a step-by-step
            roadmap with 4–8 milestones, each with specific success criteria.
          </p>

          {error && (
            <div className="mb-6 p-4 rounded-xl bg-danger-500/10 border border-danger-500/20 text-danger-400 text-sm">
              {error}
            </div>
          )}

          <button
            id="generate-roadmap-btn"
            onClick={handleGenerate}
            disabled={generating}
            className="px-8 py-3 rounded-xl bg-gradient-to-r from-primary-500 to-primary-600 text-white font-semibold text-base hover:from-primary-400 hover:to-primary-500 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-primary-500/25 hover:shadow-primary-500/40 hover:-translate-y-0.5"
          >
            {generating ? (
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                AI is crafting your roadmap…
              </span>
            ) : (
              '✨ Generate My Learning Roadmap'
            )}
          </button>

          <p className="mt-4 text-xs text-surface-600">
            Takes 10–20 seconds · Personalized to your profile
          </p>
        </div>
      </div>
    );
  }

  // ── Roadmap view ────────────────────────────────────────────────
  return (
    <div className="min-h-screen">
      <AppNavbar />
      <div className="max-w-3xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold text-surface-100">Your Learning Roadmap</h1>
              <p className="text-surface-400 text-sm mt-1">
                Personalized plan · {totalMilestones} milestones · {totalDays} days estimated
              </p>
            </div>
            <button
              onClick={() => navigate('/tasks')}
              id="go-to-tasks-btn"
              className="px-5 py-2 rounded-xl bg-primary-500/10 text-primary-400 border border-primary-500/20 text-sm font-semibold hover:bg-primary-500/20 transition-all"
            >
              My Tasks →
            </button>
          </div>

          {/* Overall progress */}
          <div className="mt-6 p-4 rounded-2xl bg-surface-900/60 border border-surface-800/40">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold text-surface-300">Overall Progress</span>
              <span className="text-sm font-bold text-primary-400">{overallPct}%</span>
            </div>
            <div className="h-2 bg-surface-800 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-primary-500 to-accent-500 transition-all duration-1000"
                style={{ width: `${overallPct}%` }}
              />
            </div>
            <div className="flex justify-between mt-2 text-xs text-surface-500">
              <span>{totalCompleted}/{totalMilestones} milestones</span>
              <span>{totalTasksCompleted}/{totalTasksPlanned} tasks</span>
            </div>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-xl bg-danger-500/10 border border-danger-500/20 text-danger-400 text-sm">
            {error}
          </div>
        )}

        {/* Milestone list */}
        <div className="space-y-6">
          {roadmap!.milestones.map((milestone, index) => (
            <MilestoneCard key={milestone.order} milestone={milestone} index={index} />
          ))}
        </div>

        {/* Footer CTA */}
        <div className="mt-8 p-5 rounded-2xl bg-gradient-to-r from-primary-500/10 to-accent-500/10 border border-primary-500/20 text-center">
          <p className="text-surface-300 text-sm mb-3">Ready to start learning?</p>
          <button
            onClick={() => navigate('/tasks')}
            className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-primary-500 to-primary-600 text-white font-semibold text-sm hover:from-primary-400 hover:to-primary-500 transition-all shadow-lg shadow-primary-500/20"
          >
            Get My Next Task →
          </button>
        </div>
      </div>
    </div>
  );
}
