/**
 * Multi-Step Onboarding Wizard — Agent 1 Profile Generation.
 *
 * Steps:
 * 1. Education Details (degree, branch, year, institution)
 * 2. Current Skills & Background (free-text narrative)
 * 3. Target Role Selection (curated role cards + custom input)
 * 4. Experience Level (student, fresher, 1-2yrs, 2+yrs)
 *
 * Immutability notice:
 * Informs candidate that upon final submission, their baseline profile
 * will be permanently locked and analyzed by Agent 1.
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getMyProfile, submitOnboarding } from '../services/profile';
import type { ExperienceLevel, OnboardingFormData } from '../types/profile';

const CURATED_ROLES = [
  {
    id: 'Full Stack Engineer',
    title: 'Full Stack Engineer',
    icon: '⚡',
    desc: 'React, Node/Python, APIs, databases & full-lifecycle systems',
  },
  {
    id: 'Frontend Engineer',
    title: 'Frontend Engineer',
    icon: '🎨',
    desc: 'Modern web UI, React/TypeScript, performance & user experience',
  },
  {
    id: 'Backend Engineer',
    title: 'Backend Engineer',
    icon: '⚙️',
    desc: 'Distributed systems, microservices, databases & cloud APIs',
  },
  {
    id: 'AI & ML Engineer',
    title: 'AI & ML Engineer',
    icon: '🧠',
    desc: 'Machine learning, LLMs, neural networks & data pipelines',
  },
  {
    id: 'DevOps & Cloud Engineer',
    title: 'DevOps & Cloud Engineer',
    icon: '☁️',
    desc: 'Docker, Kubernetes, CI/CD pipelines & AWS/GCP infrastructure',
  },
  {
    id: 'Data Engineer',
    title: 'Data Engineer',
    icon: '📊',
    desc: 'ETL pipelines, data warehousing, SQL optimization & analytics',
  },
];

const EXPERIENCE_LEVELS: { id: ExperienceLevel; title: string; desc: string }[] = [
  { id: 'student', title: 'Student', desc: 'Currently enrolled in university or college' },
  { id: 'fresher', title: 'Fresher', desc: 'Recent graduate / 0 to 1 year of experience' },
  { id: '1-2yrs', title: '1 – 2 Years', desc: 'Junior / Associate engineer working in tech' },
  { id: '2+yrs', title: '2+ Years', desc: 'Experienced developer transitioning or leveling up' },
];

export default function OnboardingPage() {
  const navigate = useNavigate();

  // Wizard step: 1..4
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [checkingExisting, setCheckingExisting] = useState<boolean>(true);

  // Form State
  const [degree, setDegree] = useState('');
  const [branch, setBranch] = useState('');
  const [year, setYear] = useState<number>(new Date().getFullYear());
  const [institution, setInstitution] = useState('');
  const [skillsDescription, setSkillsDescription] = useState('');
  const [targetRole, setTargetRole] = useState(CURATED_ROLES[0].id);
  const [customRole, setCustomRole] = useState('');
  const [isCustomRole, setIsCustomRole] = useState(false);
  const [experienceLevel, setExperienceLevel] = useState<ExperienceLevel>('fresher');

  // Submission State
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loadingPhase, setLoadingPhase] = useState('Initializing Agent 1...');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Check if profile is already finalized and locked on load
  useEffect(() => {
    async function checkExistingProfile() {
      try {
        const profile = await getMyProfile();
        if (profile && profile.is_locked) {
          // Already locked — redirect directly to dashboard
          navigate('/dashboard', { replace: true });
          return;
        }
      } catch {
        // 404 is expected when onboarding is pending
      } finally {
        setCheckingExisting(false);
      }
    }
    checkExistingProfile();
  }, [navigate]);

  // Loading animation message rotation
  useEffect(() => {
    if (!isSubmitting) return;

    const messages = [
      'Agent 1 analyzing raw background...',
      'Normalizing skills into canonical taxonomy...',
      'Assessing proficiency levels & confidence scores...',
      'Calculating deterministic readiness score...',
      'Finalizing immutable student profile...',
    ];
    let index = 0;
    const interval = setInterval(() => {
      index = (index + 1) % messages.length;
      setLoadingPhase(messages[index]);
    }, 1500);

    return () => clearInterval(interval);
  }, [isSubmitting]);

  // Step 1 Validation
  const validateStep1 = () => {
    return degree.trim().length >= 2 && branch.trim().length >= 2 && institution.trim().length >= 2 && year >= 1970;
  };

  // Step 2 Validation
  const validateStep2 = () => {
    return skillsDescription.trim().length >= 10;
  };

  const handleNext = () => {
    setErrorMessage(null);
    if (currentStep === 1 && !validateStep1()) {
      setErrorMessage('Please fill in all education fields.');
      return;
    }
    if (currentStep === 2 && !validateStep2()) {
      setErrorMessage('Please provide at least a few sentences describing your skills or projects (minimum 10 characters).');
      return;
    }
    setCurrentStep((prev) => Math.min(prev + 1, 4));
  };

  const handleBack = () => {
    setErrorMessage(null);
    setCurrentStep((prev) => Math.max(prev - 1, 1));
  };

  const handleSubmit = async () => {
    setErrorMessage(null);
    setIsSubmitting(true);

    const finalRole = isCustomRole && customRole.trim() ? customRole.trim() : targetRole;

    const payload: OnboardingFormData = {
      education: {
        degree: degree.trim(),
        branch: branch.trim(),
        year: Number(year),
        institution: institution.trim(),
      },
      skills_description: skillsDescription.trim(),
      target_role: finalRole,
      experience_level: experienceLevel,
    };

    try {
      await submitOnboarding(payload);
      // On success, redirect to Dashboard
      navigate('/dashboard', { replace: true });
    } catch (err: unknown) {
      setIsSubmitting(false);
      const apiErr = err as { response?: { status?: number; data?: { detail?: string } } };
      if (apiErr.response?.status === 403) {
        setErrorMessage('Your profile is already locked. Redirecting to dashboard...');
        setTimeout(() => navigate('/dashboard', { replace: true }), 1500);
      } else {
        setErrorMessage(
          apiErr.response?.data?.detail ||
          'Failed to process profile with AI Agent. Please verify your connection and try again.'
        );
      }
    }
  };

  if (checkingExisting) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-3 border-primary-500/20 border-t-primary-500 rounded-full animate-spin" />
          <p className="text-surface-200/60 text-sm">Checking profile status...</p>
        </div>
      </div>
    );
  }

  // Active AI Processing State
  if (isSubmitting) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6">
        <div className="max-w-md w-full bg-surface-900/70 border border-primary-500/30 backdrop-blur-2xl rounded-3xl p-10 text-center shadow-2xl relative overflow-hidden">
          {/* Glowing background halo */}
          <div className="absolute -top-24 -left-24 w-60 h-60 bg-primary-500/15 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute -bottom-24 -right-24 w-60 h-60 bg-accent-500/15 rounded-full blur-3xl pointer-events-none" />

          {/* Animated AI Pulse Icon */}
          <div className="relative w-20 h-20 mx-auto mb-6 flex items-center justify-center">
            <div className="absolute inset-0 rounded-2xl bg-gradient-to-tr from-primary-500 to-accent-400 opacity-25 animate-ping" />
            <div className="relative w-16 h-16 rounded-2xl bg-gradient-to-tr from-primary-500 to-accent-500 flex items-center justify-center shadow-lg shadow-primary-500/20">
              <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
              </svg>
            </div>
          </div>

          <h2 className="text-xl font-bold text-surface-50 mb-2">Agent 1 Analyzing Profile</h2>
          <p className="text-sm font-medium text-primary-400 mb-4 h-6 transition-all duration-300">
            {loadingPhase}
          </p>
          <p className="text-xs text-surface-200/50 leading-relaxed">
            Our AI engine is parsing your project experience, mapping skills against industry taxonomies,
            and establishing your baseline dashboard.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col py-10 px-4 sm:px-6">
      {/* Top Header / Progress */}
      <div className="max-w-2xl mx-auto w-full mb-8 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary-500/10 border border-primary-400/20 text-xs font-semibold text-primary-300 mb-3">
          <span>AI Career Agent 1</span>
          <span>•</span>
          <span>Profile Onboarding</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold text-surface-50 tracking-tight">
          Let’s Build Your Career Profile
        </h1>
        <p className="text-sm text-surface-200/60 mt-1">
          Tell us about your background so Agent 1 can assess your competencies and generate your personalized dashboard.
        </p>

        {/* Stepper Progress Bar */}
        <div className="mt-8 flex items-center justify-between relative max-w-md mx-auto">
          <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-surface-800 -translate-y-1/2 -z-0" />
          <div
            className="absolute top-1/2 left-0 h-0.5 bg-primary-500 -translate-y-1/2 transition-all duration-500 -z-0"
            style={{ width: `${((currentStep - 1) / 3) * 100}%` }}
          />

          {[
            { num: 1, label: 'Education' },
            { num: 2, label: 'Skills' },
            { num: 3, label: 'Goal' },
            { num: 4, label: 'Experience' },
          ].map((st) => {
            const isCompleted = currentStep > st.num;
            const isCurrent = currentStep === st.num;
            return (
              <div key={st.num} className="flex flex-col items-center z-10">
                <div
                  className={`w-9 h-9 rounded-full flex items-center justify-center font-semibold text-xs transition-all duration-300 ${
                    isCurrent
                      ? 'bg-primary-500 text-white shadow-lg shadow-primary-500/30 ring-4 ring-primary-500/20'
                      : isCompleted
                      ? 'bg-accent-500 text-white'
                      : 'bg-surface-800 text-surface-200/50 border border-surface-700/50'
                  }`}
                >
                  {isCompleted ? '✓' : st.num}
                </div>
                <span className={`text-[11px] font-medium mt-1.5 ${isCurrent ? 'text-primary-300' : 'text-surface-200/50'}`}>
                  {st.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Main Card Container */}
      <div className="max-w-2xl mx-auto w-full bg-surface-900/50 backdrop-blur-xl border border-surface-700/30 rounded-3xl p-6 sm:p-8 shadow-2xl relative">
        {errorMessage && (
          <div className="mb-6 p-4 rounded-2xl bg-danger-500/10 border border-danger-500/20 text-danger-400 text-sm flex items-center gap-3">
            <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span>{errorMessage}</span>
          </div>
        )}

        {/* STEP 1: Education Details */}
        {currentStep === 1 && (
          <div className="space-y-5 animate-in fade-in duration-300">
            <div>
              <h2 className="text-lg font-bold text-surface-50">Step 1: Educational Background</h2>
              <p className="text-xs text-surface-200/60 mt-0.5">
                Where did you study, and what degree are you pursuing or holding?
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-surface-200 mb-1.5">
                  Degree / Program *
                </label>
                <input
                  type="text"
                  placeholder="e.g. B.Tech, B.S., M.S., BCA"
                  value={degree}
                  onChange={(e) => setDegree(e.target.value)}
                  className="w-full px-4 py-2.5 bg-surface-950/60 border border-surface-700/50 rounded-xl text-surface-50 text-sm focus:border-primary-400 transition"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-surface-200 mb-1.5">
                  Branch / Major *
                </label>
                <input
                  type="text"
                  placeholder="e.g. Computer Science, IT, Data Sci"
                  value={branch}
                  onChange={(e) => setBranch(e.target.value)}
                  className="w-full px-4 py-2.5 bg-surface-950/60 border border-surface-700/50 rounded-xl text-surface-50 text-sm focus:border-primary-400 transition"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-surface-200 mb-1.5">
                  Graduation Year *
                </label>
                <input
                  type="number"
                  min="1970"
                  max="2035"
                  value={year}
                  onChange={(e) => setYear(Number(e.target.value))}
                  className="w-full px-4 py-2.5 bg-surface-950/60 border border-surface-700/50 rounded-xl text-surface-50 text-sm focus:border-primary-400 transition"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-surface-200 mb-1.5">
                  College / University *
                </label>
                <input
                  type="text"
                  placeholder="e.g. Stanford University"
                  value={institution}
                  onChange={(e) => setInstitution(e.target.value)}
                  className="w-full px-4 py-2.5 bg-surface-950/60 border border-surface-700/50 rounded-xl text-surface-50 text-sm focus:border-primary-400 transition"
                />
              </div>
            </div>
          </div>
        )}

        {/* STEP 2: Skills & Narrative */}
        {currentStep === 2 && (
          <div className="space-y-4 animate-in fade-in duration-300">
            <div>
              <h2 className="text-lg font-bold text-surface-50">Step 2: Skills & Project Experience</h2>
              <p className="text-xs text-surface-200/60 mt-0.5">
                Describe in your own words the languages you know, frameworks you have used, projects you built, or topics you have learned.
              </p>
            </div>

            <div className="bg-surface-950/40 border border-surface-700/30 rounded-2xl p-3.5 text-xs text-surface-200/70 space-y-1">
              <span className="font-semibold text-primary-300">💡 Tip: Be descriptive! Mention:</span>
              <ul className="list-disc list-inside space-y-0.5 pl-1 text-surface-200/60">
                <li>Programming languages you are comfortable with (e.g. Python, JavaScript, Java)</li>
                <li>Key frameworks or databases (e.g. React, FastAPI, PostgreSQL, MongoDB, Docker)</li>
                <li>Real projects, apps, hackathons, or coursework you have completed</li>
              </ul>
            </div>

            <div>
              <textarea
                rows={7}
                placeholder="Example: I have built a full-stack e-commerce project using React, Tailwind CSS, and Python FastAPI. I used PostgreSQL with SQLAlchemy for data persistence and Docker for containerization. I also have foundational knowledge of Data Structures and Git..."
                value={skillsDescription}
                onChange={(e) => setSkillsDescription(e.target.value)}
                className="w-full px-4 py-3 bg-surface-950/60 border border-surface-700/50 rounded-2xl text-surface-50 text-sm focus:border-primary-400 transition resize-none leading-relaxed"
              />
              <div className="flex justify-between text-xs text-surface-200/40 mt-1">
                <span>Minimum 10 characters</span>
                <span>{skillsDescription.length} characters</span>
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: Target Role Selection */}
        {currentStep === 3 && (
          <div className="space-y-4 animate-in fade-in duration-300">
            <div>
              <h2 className="text-lg font-bold text-surface-50">Step 3: What is Your Target Role?</h2>
              <p className="text-xs text-surface-200/60 mt-0.5">
                Select your primary career aspiration. Agent 1 will calibrate your skill readiness against this target.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {CURATED_ROLES.map((role) => {
                const isSelected = !isCustomRole && targetRole === role.id;
                return (
                  <button
                    key={role.id}
                    type="button"
                    onClick={() => {
                      setIsCustomRole(false);
                      setTargetRole(role.id);
                    }}
                    className={`text-left p-4 rounded-2xl border transition-all duration-200 cursor-pointer ${
                      isSelected
                        ? 'bg-primary-500/15 border-primary-400 ring-2 ring-primary-500/20'
                        : 'bg-surface-950/40 border-surface-700/40 hover:border-surface-700/80 hover:bg-surface-800/30'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-lg">{role.icon}</span>
                      <span className={`text-sm font-semibold ${isSelected ? 'text-primary-300' : 'text-surface-100'}`}>
                        {role.title}
                      </span>
                    </div>
                    <p className="text-xs text-surface-200/50 leading-snug">{role.desc}</p>
                  </button>
                );
              })}
            </div>

            {/* Custom role toggle */}
            <div className="pt-2">
              <label className="flex items-center gap-2 cursor-pointer text-xs text-surface-200/70 mb-2">
                <input
                  type="checkbox"
                  checked={isCustomRole}
                  onChange={(e) => setIsCustomRole(e.target.checked)}
                  className="rounded border-surface-700 text-primary-500 focus:ring-primary-500"
                />
                <span>Target a different / specialized role</span>
              </label>

              {isCustomRole && (
                <input
                  type="text"
                  placeholder="e.g. Security Engineer, iOS Developer, Embedded Systems"
                  value={customRole}
                  onChange={(e) => setCustomRole(e.target.value)}
                  className="w-full px-4 py-2.5 bg-surface-950/60 border border-surface-700/50 rounded-xl text-surface-50 text-sm focus:border-primary-400 transition"
                />
              )}
            </div>
          </div>
        )}

        {/* STEP 4: Experience Level & Final Review */}
        {currentStep === 4 && (
          <div className="space-y-5 animate-in fade-in duration-300">
            <div>
              <h2 className="text-lg font-bold text-surface-50">Step 4: Experience Level</h2>
              <p className="text-xs text-surface-200/60 mt-0.5">
                Select your current career seniority bracket.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {EXPERIENCE_LEVELS.map((lvl) => {
                const isSelected = experienceLevel === lvl.id;
                return (
                  <button
                    key={lvl.id}
                    type="button"
                    onClick={() => setExperienceLevel(lvl.id)}
                    className={`text-left p-4 rounded-2xl border transition-all duration-200 cursor-pointer ${
                      isSelected
                        ? 'bg-primary-500/15 border-primary-400 ring-2 ring-primary-500/20'
                        : 'bg-surface-950/40 border-surface-700/40 hover:border-surface-700/80 hover:bg-surface-800/30'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className={`text-sm font-semibold ${isSelected ? 'text-primary-300' : 'text-surface-100'}`}>
                        {lvl.title}
                      </span>
                      {isSelected && <span className="text-primary-400 text-sm">●</span>}
                    </div>
                    <p className="text-xs text-surface-200/50 leading-snug">{lvl.desc}</p>
                  </button>
                );
              })}
            </div>

            {/* Immutability & Lock Notice */}
            <div className="p-4 rounded-2xl bg-surface-950/70 border border-surface-700/40 flex items-start gap-3">
              <span className="text-xl">🔒</span>
              <div className="text-xs text-surface-200/70 space-y-1">
                <span className="font-semibold text-surface-100">Baseline Lock Policy:</span>
                <p className="leading-relaxed">
                  Upon final submission, Agent 1 will permanently lock this baseline profile.
                  This ensures consistent roadmap planning and unbiased skill progression tracking.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Wizard Controls */}
        <div className="mt-8 pt-5 border-t border-surface-700/30 flex items-center justify-between">
          {currentStep > 1 ? (
            <button
              type="button"
              onClick={handleBack}
              className="px-5 py-2.5 rounded-xl border border-surface-700/50 text-surface-200 text-xs font-semibold hover:bg-surface-800/50 transition cursor-pointer"
            >
              ← Back
            </button>
          ) : (
            <div />
          )}

          {currentStep < 4 ? (
            <button
              type="button"
              onClick={handleNext}
              className="px-6 py-2.5 rounded-xl bg-primary-500 hover:bg-primary-600 text-white text-xs font-semibold shadow-lg shadow-primary-500/20 transition cursor-pointer"
            >
              Continue →
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              className="px-7 py-2.5 rounded-xl bg-gradient-to-r from-primary-500 to-accent-500 hover:from-primary-600 hover:to-accent-600 text-white text-xs font-semibold shadow-lg shadow-primary-500/25 transition cursor-pointer flex items-center gap-2"
            >
              <span>Analyze & Build Profile</span>
              <span>✨</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
