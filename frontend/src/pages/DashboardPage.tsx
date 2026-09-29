/**
 * Dashboard Page — Displays the AI-analyzed Student Profile.
 *
 * Visualizes:
 * - Target Career Goal & Seniority
 * - Deterministic Readiness Score with component breakdown
 * - Strongest vs Weakest competency domains
 * - Categorized Skills Matrix with proficiency badges & confidence bars
 * - Immutability lock indicator
 * - Education & Audit information
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getMyProfile } from '../services/profile';
import { getMyRoadmap } from '../services/roadmap';
import type { Roadmap } from '../services/roadmap';
import type { SkillItem, StudentProfile } from '../types/profile';

export default function DashboardPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [showRawInput, setShowRawInput] = useState(false);
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadData() {
      try {
        const data = await getMyProfile();
        if (isMounted) {
          setProfile(data);
          setIsLoading(false);
        }
        try {
          const rm = await getMyRoadmap();
          if (isMounted) setRoadmap(rm);
        } catch {
          // No roadmap or error - harmless for dashboard
        }
      } catch (err: unknown) {
        // If profile does not exist (404), redirect straight to onboarding
        const apiErr = err as { response?: { status?: number } };
        if (apiErr.response?.status === 404) {
          navigate('/onboarding', { replace: true });
        } else {
          if (isMounted) setIsLoading(false);
        }
      }
    }

    loadData();
    return () => {
      isMounted = false;
    };
  }, [navigate]);

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-3 border-primary-500/20 border-t-primary-500 rounded-full animate-spin" />
          <p className="text-surface-200/60 text-sm">Loading your career dashboard...</p>
        </div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6">
        <div className="max-w-md w-full bg-surface-900/50 border border-surface-700/40 rounded-3xl p-8 text-center">
          <h2 className="text-lg font-bold text-surface-50 mb-2">Profile Incomplete</h2>
          <p className="text-sm text-surface-200/60 mb-6">
            You have not completed the initial onboarding assessment.
          </p>
          <button
            onClick={() => navigate('/onboarding')}
            className="px-6 py-2.5 bg-primary-500 hover:bg-primary-600 text-white rounded-xl text-xs font-semibold"
          >
            Start Onboarding →
          </button>
        </div>
      </div>
    );
  }

  // Filter skills by category
  const categories = ['All', ...Object.keys(profile.dashboard_data.skill_distribution || {})];
  const filteredSkills =
    selectedCategory === 'All'
      ? profile.structured_skills
      : profile.structured_skills.filter((s) => s.category === selectedCategory);

  const readiness = profile.dashboard_data.readiness_score;

  // Determine readiness level label & color
  let readinessTier = { label: 'Foundational', color: 'text-amber-400', stroke: '#fbbf24', bg: 'bg-amber-400/10' };
  if (readiness >= 75) {
    readinessTier = { label: 'Production Ready', color: 'text-emerald-400', stroke: '#34d399', bg: 'bg-emerald-400/10' };
  } else if (readiness >= 50) {
    readinessTier = { label: 'Intermediate Competence', color: 'text-primary-400', stroke: '#38bdf8', bg: 'bg-primary-400/10' };
  }

  // Roadmap progress computation for summary card
  const currentMilestone = roadmap?.milestones.find((m) => m.state === 'current') ||
    roadmap?.milestones.find((m) => m.state === 'upcoming');
  const completedTasksCount = roadmap?.milestones.reduce((acc, m) => acc + m.tasks_completed, 0) || 0;
  const totalPlannedTasks = roadmap?.milestones.reduce((acc, m) => acc + m.tasks_planned, 0) || 0;
  const progressPct = totalPlannedTasks > 0 ? Math.round((completedTasksCount / totalPlannedTasks) * 100) : 0;

  return (
    <div className="min-h-screen flex flex-col pb-16">
      {/* Navigation bar */}
      <nav className="border-b border-surface-700/30 bg-surface-900/40 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary-500/15 border border-primary-400/20 flex items-center justify-center">
              <svg className="w-5 h-5 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.636 50.636 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342M6.75 15a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm0 0v-3.675A55.378 55.378 0 0 1 12 8.443m-7.007 11.55A5.981 5.981 0 0 0 6.75 15.75v-1.5" />
              </svg>
            </div>
            <div>
              <span className="font-semibold text-surface-50 tracking-tight text-sm">Career Platform</span>
              <span className="hidden sm:inline-block ml-2 text-[11px] px-2 py-0.5 rounded-full bg-surface-800 text-surface-200/60 border border-surface-700/50">
                Agents 1 & 2 Active
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Week 3 navigation links */}
            <nav className="hidden md:flex items-center gap-1">
              <button
                onClick={() => navigate('/dashboard')}
                className="px-3 py-1.5 text-xs font-medium text-surface-100 bg-surface-800/80 rounded-lg transition-all"
              >
                Dashboard
              </button>
              <button
                onClick={() => navigate('/roadmap')}
                id="nav-roadmap"
                className="px-3 py-1.5 text-xs font-medium text-surface-300 hover:text-surface-100 hover:bg-surface-800/60 rounded-lg transition-all"
              >
                Roadmap
              </button>
              <button
                onClick={() => navigate('/tasks')}
                id="nav-tasks"
                className="px-3 py-1.5 text-xs font-medium text-primary-400 hover:text-primary-300 hover:bg-primary-500/10 rounded-lg transition-all border border-primary-500/20"
              >
                ⚡ Daily Task
              </button>
              <button
                onClick={() => navigate('/history')}
                id="nav-history"
                className="px-3 py-1.5 text-xs font-medium text-surface-300 hover:text-surface-100 hover:bg-surface-800/60 rounded-lg transition-all"
              >
                History
              </button>
            </nav>
            <span className="text-xs text-surface-200/70 hidden sm:block">{user?.email}</span>
            <button
              onClick={handleLogout}
              id="dashboard-logout"
              className="px-3.5 py-1.5 text-xs font-medium text-surface-200 bg-surface-800/60 hover:bg-surface-700/60 border border-surface-700/40 rounded-xl transition cursor-pointer"
            >
              Sign out
            </button>
          </div>
        </div>
      </nav>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-6 pt-8 space-y-8">
        {/* Profile Hero Header */}
        <div className="bg-surface-900/50 backdrop-blur-xl border border-surface-700/30 rounded-3xl p-6 sm:p-8 relative overflow-hidden shadow-xl">
          <div className="absolute top-0 right-0 w-80 h-80 bg-primary-500/10 rounded-full blur-3xl pointer-events-none" />

          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
            <div>
              <div className="flex flex-wrap items-center gap-2.5 mb-2">
                <span className="px-3 py-1 rounded-full bg-primary-500/15 border border-primary-400/30 text-xs font-semibold text-primary-300">
                  Target: {profile.target_role}
                </span>
                <span className="px-3 py-1 rounded-full bg-surface-800/80 border border-surface-700/50 text-xs font-medium text-surface-200 capitalize">
                  Level: {profile.experience_level}
                </span>
                <span className="px-3 py-1 rounded-full bg-accent-500/15 border border-accent-400/30 text-xs font-semibold text-accent-400 flex items-center gap-1.5">
                  <span>🔒</span>
                  <span>Baseline Locked</span>
                </span>
              </div>

              <h1 className="text-2xl sm:text-3xl font-extrabold text-surface-50 tracking-tight">
                {profile.education.degree} in {profile.education.branch}
              </h1>
              <p className="text-sm text-surface-200/60 mt-1">
                {profile.education.institution} • Graduating Class of {profile.education.year}
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setShowRawInput(!showRawInput)}
                className="px-4 py-2 rounded-xl bg-surface-800/70 hover:bg-surface-800 border border-surface-700/50 text-xs font-medium text-surface-200 transition cursor-pointer"
              >
                {showRawInput ? 'Hide Raw Input' : 'Inspect Audit Input'}
              </button>
            </div>
          </div>

          {/* Audit Raw Input Accordion */}
          {showRawInput && (
            <div className="mt-6 pt-6 border-t border-surface-700/40 text-xs text-surface-200/80 space-y-2 animate-in fade-in">
              <span className="font-semibold text-primary-300">Raw Narrative Submitted (Audit Trail):</span>
              <p className="bg-surface-950/70 p-4 rounded-2xl border border-surface-700/30 font-mono text-[11px] leading-relaxed whitespace-pre-wrap">
                {profile.raw_input.skills_description}
              </p>
            </div>
          )}
        </div>

        {/* Top Analytics Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Readiness Score Card */}
          <div className="bg-surface-900/50 backdrop-blur-xl border border-surface-700/30 rounded-3xl p-6 flex flex-col justify-between shadow-lg">
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-bold text-surface-200/70 uppercase tracking-wider">
                Role Readiness Score
              </span>
              <span className={`text-[11px] font-semibold px-2.5 py-0.5 rounded-full ${readinessTier.bg} ${readinessTier.color}`}>
                {readinessTier.label}
              </span>
            </div>

            <div className="flex items-center gap-6 my-2">
              {/* Circular Gauge */}
              <div className="relative w-24 h-24 flex items-center justify-center flex-shrink-0">
                <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
                  <path
                    className="text-surface-800"
                    strokeWidth="3.5"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                  <path
                    stroke={readinessTier.stroke}
                    strokeDasharray={`${readiness}, 100`}
                    strokeLinecap="round"
                    strokeWidth="3.5"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                </svg>
                <div className="absolute text-center">
                  <span className="text-2xl font-black text-surface-50">{readiness}</span>
                  <span className="text-[10px] text-surface-200/50 block -mt-1">/100</span>
                </div>
              </div>

              <div className="space-y-1">
                <p className="text-xs font-medium text-surface-100 leading-snug">
                  Deterministic readiness calculation based on validated competencies.
                </p>
                <p className="text-[11px] text-surface-200/50">
                  Calibrated for {profile.target_role}.
                </p>
              </div>
            </div>

            <p className="text-[11px] text-surface-200/60 mt-3 pt-3 border-t border-surface-700/30 leading-relaxed">
              {profile.dashboard_data.readiness_summary}
            </p>
          </div>

          {/* Strongest Competencies */}
          <div className="bg-surface-900/50 backdrop-blur-xl border border-surface-700/30 rounded-3xl p-6 flex flex-col justify-between shadow-lg">
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs font-bold text-surface-200/70 uppercase tracking-wider">
                  Top Strength Domains
                </span>
                <span className="text-base">🚀</span>
              </div>
              <p className="text-xs text-surface-200/60 mb-4">
                Areas where your technical foundation and confidence are most solidified:
              </p>

              <div className="space-y-2.5">
                {profile.dashboard_data.strongest_areas.length > 0 ? (
                  profile.dashboard_data.strongest_areas.map((area) => (
                    <div
                      key={area}
                      className="flex items-center justify-between p-3 rounded-2xl bg-surface-950/40 border border-surface-700/40"
                    >
                      <span className="text-xs font-semibold text-surface-100">{area}</span>
                      <span className="text-[11px] font-bold text-accent-400">
                        {profile.dashboard_data.category_averages?.[area]
                          ? `${profile.dashboard_data.category_averages[area]} / 3.0`
                          : 'High'}
                      </span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-surface-200/40">Competencies distributed evenly.</p>
                )}
              </div>
            </div>

            <p className="text-[11px] text-surface-200/40 mt-4 pt-3 border-t border-surface-700/30">
              Identified through Agent 1 semantic extraction.
            </p>
          </div>

          {/* Growth & Roadmap Focus Areas */}
          <div className="bg-surface-900/50 backdrop-blur-xl border border-surface-700/30 rounded-3xl p-6 flex flex-col justify-between shadow-lg">
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs font-bold text-surface-200/70 uppercase tracking-wider">
                  Target Role Growth Focus
                </span>
                <span className="text-base">🎯</span>
              </div>
              <p className="text-xs text-surface-200/60 mb-4">
                Key domains to expand to maximize {profile.target_role} market readiness:
              </p>

              <div className="space-y-2.5">
                {profile.dashboard_data.weakest_areas.length > 0 ? (
                  profile.dashboard_data.weakest_areas.map((area) => (
                    <div
                      key={area}
                      className="flex items-center justify-between p-3 rounded-2xl bg-surface-950/40 border border-surface-700/40"
                    >
                      <span className="text-xs font-semibold text-surface-100">{area}</span>
                      <span className="text-[11px] font-semibold text-primary-300">Roadmap Focus</span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-surface-200/40">Broad domain coverage established.</p>
                )}
              </div>
            </div>

            <p className="text-[11px] text-surface-200/40 mt-4 pt-3 border-t border-surface-700/30">
              Agent 2 generates adaptive learning paths targeting these gaps.
            </p>
          </div>
        </div>

        {/* Agent 2: Learning Roadmap & Daily Task Progress Summary Card */}
        <div className="bg-surface-900/50 backdrop-blur-xl border border-surface-700/30 rounded-3xl p-6 sm:p-8 shadow-xl relative overflow-hidden">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-primary-400 animate-pulse" />
                <span className="text-xs font-bold text-primary-400 uppercase tracking-wider">
                  Agent 2 • Roadmap & Daily Task
                </span>
              </div>
              {roadmap ? (
                <div>
                  <h2 className="text-xl font-bold text-surface-50">
                    {currentMilestone
                      ? `Milestone ${currentMilestone.order}: ${currentMilestone.title}`
                      : 'All Milestones Completed!'}
                  </h2>
                  <p className="text-xs text-surface-200/70 mt-1">
                    {completedTasksCount} of {totalPlannedTasks} tasks completed across {roadmap.milestones.length} milestones
                  </p>
                </div>
              ) : (
                <div>
                  <h2 className="text-xl font-bold text-surface-50">No Learning Roadmap Yet</h2>
                  <p className="text-xs text-surface-200/70 mt-1">
                    Generate an AI-powered personalized curriculum based on your locked profile baseline.
                  </p>
                </div>
              )}
            </div>

            <div className="flex items-center gap-3">
              {roadmap ? (
                <>
                  <button
                    onClick={() => navigate('/roadmap')}
                    className="px-4 py-2.5 rounded-xl bg-surface-800 hover:bg-surface-700 border border-surface-700 text-xs font-semibold text-surface-200 transition cursor-pointer"
                  >
                    View Roadmap →
                  </button>
                  <button
                    onClick={() => navigate('/tasks')}
                    id="dashboard-go-to-task-btn"
                    className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-primary-500 to-primary-600 hover:from-primary-400 hover:to-primary-500 text-white text-xs font-semibold shadow-lg shadow-primary-500/20 transition cursor-pointer"
                  >
                    ⚡ Continue Daily Task →
                  </button>
                </>
              ) : (
                <button
                  onClick={() => navigate('/roadmap')}
                  id="dashboard-generate-roadmap-btn"
                  className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-primary-500 to-primary-600 hover:from-primary-400 hover:to-primary-500 text-white text-xs font-semibold shadow-lg shadow-primary-500/25 transition cursor-pointer"
                >
                  ✨ Generate Roadmap →
                </button>
              )}
            </div>
          </div>

          {roadmap && (
            <div className="mt-6 pt-5 border-t border-surface-700/30">
              <div className="flex items-center justify-between text-xs mb-2">
                <span className="text-surface-300 font-medium">Curriculum Progress</span>
                <span className="text-primary-400 font-bold">{progressPct}%</span>
              </div>
              <div className="h-2 bg-surface-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-primary-500 to-accent-500 rounded-full transition-all duration-700"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Structured Skills Inventory Matrix */}
        <div className="bg-surface-900/50 backdrop-blur-xl border border-surface-700/30 rounded-3xl p-6 sm:p-8 shadow-xl">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div>
              <h2 className="text-lg font-bold text-surface-50">Structured Technical Competencies</h2>
              <p className="text-xs text-surface-200/60 mt-0.5">
                {profile.structured_skills.length} skills parsed, categorized, and evaluated with confidence scores.
              </p>
            </div>

            {/* Category Filter Pills */}
            <div className="flex flex-wrap gap-1.5">
              {categories.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition cursor-pointer ${
                    selectedCategory === cat
                      ? 'bg-primary-500 text-white shadow-md shadow-primary-500/25'
                      : 'bg-surface-800/60 text-surface-200/70 hover:bg-surface-800 border border-surface-700/40'
                  }`}
                >
                  {cat}
                  {cat !== 'All' && (
                    <span className="ml-1.5 text-[10px] opacity-75">
                      ({profile.dashboard_data.skill_distribution[cat] || 0})
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Skills Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredSkills.map((skill: SkillItem) => {
              // Proficiency Badge Color
              let profBadge = {
                label: 'Beginner',
                bg: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
              };
              if (skill.proficiency_level === 'intermediate') {
                profBadge = {
                  label: 'Intermediate',
                  bg: 'bg-primary-500/15 text-primary-300 border-primary-500/30',
                };
              } else if (skill.proficiency_level === 'advanced') {
                profBadge = {
                  label: 'Advanced',
                  bg: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
                };
              }

              const confidencePercent = Math.round(skill.confidence_score * 100);

              return (
                <div
                  key={skill.skill_name}
                  className="bg-surface-950/40 border border-surface-700/40 hover:border-primary-500/40 rounded-2xl p-4.5 transition-all duration-200 group"
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div>
                      <h3 className="text-sm font-bold text-surface-50 group-hover:text-primary-300 transition">
                        {skill.skill_name}
                      </h3>
                      <span className="text-[11px] text-surface-200/50">{skill.category}</span>
                    </div>

                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${profBadge.bg}`}>
                      {profBadge.label}
                    </span>
                  </div>

                  {/* Confidence Meter */}
                  <div className="mt-3">
                    <div className="flex justify-between text-[10px] text-surface-200/50 mb-1">
                      <span>Extraction Confidence</span>
                      <span className="font-mono text-surface-200/80">{confidencePercent}%</span>
                    </div>
                    <div className="w-full h-1.5 bg-surface-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-primary-500 to-accent-400 rounded-full transition-all duration-500"
                        style={{ width: `${confidencePercent}%` }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </main>
    </div>
  );
}
