import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  User,
  GraduationCap,
  Briefcase,
  Award,
  BookOpen,
  Clock,
  Target,
  Sparkles,
  Check,
  ArrowRight,
  ArrowLeft,
  Compass,
  CheckCircle2,
  Sliders,
  Code2,
  ChevronRight,
  Flame,
  BrainCircuit,
  MapPin,
  Building,
  Calendar,
  Layers,
  AlertCircle,
} from 'lucide-react';
import Card from '../components/Card/Card';
import Button from '../components/Button/Button';
import Input from '../components/Input/Input';
import useAuth from '../hooks/useAuth';
import userService from '../services/userService';
import professionService from '../services/professionService';
import onboardingService from '../services/onboardingService';

// ─── Static UI constants (not profession-catalog data) ─────────────────────
// These lists drive UI chips only — they are NOT used to create/match professions.

const SKILL_OPTIONS = [
  'Python', 'JavaScript', 'React', 'Node.js', 'SQL', 'Git', 'Linux',
  'Docker', 'PyTorch', 'Pandas', 'NumPy', 'Scikit-learn', 'CSS',
  'TypeScript', 'Java', 'C++', 'Go', 'Rust', 'Kubernetes', 'AWS',
];

const INTEREST_OPTIONS = [
  { label: 'AI & Machine Learning', desc: 'Predictive Models, Neural Networks & MLOps' },
  { label: 'Frontend & UI Engineering', desc: 'Modern Web Apps, React & User Interfaces' },
  { label: 'Backend & Systems', desc: 'APIs, Databases, Microservices & Cloud' },
  { label: 'Data Science & Analytics', desc: 'Data Pipelines, BI Dashboards & Statistics' },
  { label: 'Cloud & DevOps', desc: 'CI/CD, Containers, Kubernetes & Cloud Infra' },
  { label: 'Cybersecurity', desc: 'Penetration Testing, Security Audits & Cryptography' },
];

// Assessment questions are fixed UX questions. The `alignment` strings are partial
// profession name hints used only for relative scoring — they do NOT resolve to IDs.
const ASSESSMENT_QUESTIONS = [
  {
    id: 1,
    question: 'Which area of problem-solving excites you the most?',
    options: [
      { text: 'Developing predictive models, feature pipelines, and machine learning algorithms', alignment: ['Machine Learning', 'Data Science'] },
      { text: 'Building responsive web interfaces, interactive components, and user-facing features', alignment: ['Frontend', 'UI'] },
      { text: 'Designing scalable APIs, databases, and distributed systems', alignment: ['Backend', 'Systems', 'Cloud'] },
    ],
  },
  {
    id: 2,
    question: 'What is your ideal project artifact?',
    options: [
      { text: 'A trained machine learning model with feature engineering and MLOps deployment', alignment: ['Machine Learning'] },
      { text: 'A modern, responsive React web application with clean component styling', alignment: ['Frontend'] },
      { text: 'A robust REST API with authentication, database ORM, and Docker deployment', alignment: ['Backend', 'Systems'] },
    ],
  },
  {
    id: 3,
    question: 'What type of daily coding activity sounds most rewarding?',
    options: [
      { text: 'Optimizing model hyper-parameters and feature transformations using Pandas & PyTorch', alignment: ['Machine Learning', 'Data Science'] },
      { text: 'Creating reusable React components, state management hooks, and UI micro-animations', alignment: ['Frontend'] },
      { text: 'Architecting microservices, writing CI/CD pipelines, and cloud infra configs', alignment: ['Backend', 'Cloud'] },
    ],
  },
];

// ─── Component ──────────────────────────────────────────────────────────────

export const OnboardingPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  // Onboarding Stage: 'profile' | 'assessment' | 'recommendation' | 'roadmap'
  const [stage, setStage] = useState('profile');
  const [currentStep, setCurrentStep] = useState(1);
  const totalProfileSteps = 9;

  // ── Backend professions state ────────────────────────────────────────────
  const [backendProfessions, setBackendProfessions] = useState([]);
  const [professionsLoading, setProfessionsLoading] = useState(true);
  const [professionsError, setProfessionsError] = useState(null);

  // Step 1: Personal & Education
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [age, setAge] = useState('');
  const [country, setCountry] = useState('India');
  const [college, setCollege] = useState('');
  const [degree, setDegree] = useState('B.Tech Computer Science');
  const [graduationYear, setGraduationYear] = useState('2026');

  // Step 2: Career Goal — stores the profession NAME string (display only)
  const [careerGoal, setCareerGoal] = useState('');

  // Step 3: Experience Level
  const [experienceLevel, setExperienceLevel] = useState('Beginner');

  // Step 4: Current Skills
  const [selectedSkills, setSelectedSkills] = useState([]);

  // Step 5: Interests
  const [selectedInterests, setSelectedInterests] = useState([]);

  // Step 6: Daily Study Time
  const [dailyStudyTime, setDailyStudyTime] = useState('1 hour');

  // Step 7: Learning Style
  const [learningStyle, setLearningStyle] = useState('Mixed');

  // Step 8: Primary Goal
  const [primaryGoal, setPrimaryGoal] = useState('Job');

  // Step 9: Difficulty Preference
  const [difficultyPreference, setDifficultyPreference] = useState('Adaptive');

  // Assessment answers state
  const [assessmentAnswers, setAssessmentAnswers] = useState({});
  const [assessmentIndex, setAssessmentIndex] = useState(0);

  // Ranked Recommendations & Selected Profession (always from backend data)
  const [recommendationResult, setRecommendationResult] = useState(null);
  const [chosenProfession, setChosenProfession] = useState(null);
  const [generatedRoadmap, setGeneratedRoadmap] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  // ── Fetch real professions from backend on mount ─────────────────────────
  useEffect(() => {
    const loadProfessions = async () => {
      try {
        setProfessionsLoading(true);
        setProfessionsError(null);
        const data = await professionService.getProfessions({ is_active: true });
        // API may return { data: [...] } or directly an array
        const list = Array.isArray(data) ? data : (data?.data || data?.items || []);
        setBackendProfessions(list);
        // Pre-select first profession name as career goal default
        if (list.length > 0 && !careerGoal) {
          setCareerGoal(list[0].name);
        }
      } catch (err) {
        console.error('Failed to load professions from backend:', err);
        setProfessionsError('Could not load professions. Please check your connection and try again.');
      } finally {
        setProfessionsLoading(false);
      }
    };
    loadProfessions();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync user full name when auth loads
  useEffect(() => {
    if (user?.full_name && !fullName) {
      setFullName(user.full_name);
    }
  }, [user]); // eslint-disable-line react-hooks/exhaustive-deps

  // Handle skill toggle
  const toggleSkill = (skill) => {
    setSelectedSkills((prev) =>
      prev.includes(skill) ? prev.filter((s) => s !== skill) : [...prev, skill]
    );
  };

  // Handle interest toggle
  const toggleInterest = (interest) => {
    setSelectedInterests((prev) =>
      prev.includes(interest) ? prev.filter((i) => i !== interest) : [...prev, interest]
    );
  };

  // Move to next step in profile wizard
  const handleNextStep = () => {
    if (currentStep < totalProfileSteps) {
      setCurrentStep((prev) => prev + 1);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      // Save wizard progress to localStorage (only wizard state, not profession data)
      const profileData = {
        fullName,
        age,
        country,
        college,
        degree,
        graduationYear,
        careerGoal,        // profession name string for scoring hint only
        experienceLevel,
        skills: selectedSkills,
        interests: selectedInterests,
        dailyStudyTime,
        learningStyle,
        primaryGoal,
        difficultyPreference,
      };
      onboardingService.saveProfile(profileData);
      setStage('assessment');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handlePrevStep = () => {
    if (currentStep > 1) {
      setCurrentStep((prev) => prev - 1);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  // Assessment question select
  const handleSelectAssessmentOption = (questionId, option) => {
    setAssessmentAnswers({
      ...assessmentAnswers,
      [questionId]: option,
    });
  };

  const handleNextAssessment = () => {
    if (assessmentIndex < ASSESSMENT_QUESTIONS.length - 1) {
      setAssessmentIndex((prev) => prev + 1);
    } else {
      // Finish Assessment — rank real backend professions using scoring logic
      const profileData = onboardingService.getProfile();
      const answersArray = Object.values(assessmentAnswers);

      // rankProfessions uses only backend-sourced profession objects
      const result = onboardingService.rankProfessions(profileData, answersArray, backendProfessions);

      if (!result) {
        // Fallback: no professions loaded — show error
        setProfessionsError('No professions available to recommend. Please contact support.');
        setStage('profile');
        return;
      }

      setRecommendationResult(result);
      setChosenProfession(result.primary);
      setStage('recommendation');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  // Confirm Profession — generates local roadmap preview & submits to backend
  const handleConfirmProfession = async (professionToSet) => {
    const targetProf = professionToSet || chosenProfession || recommendationResult?.primary;
    setChosenProfession(targetProf);
    setSubmitError(null);

    // Generate a local roadmap preview (for the onboarding roadmap stage display only)
    const profileData = onboardingService.getProfile();
    const roadmap = onboardingService.generateRoadmap(targetProf, profileData);
    setGeneratedRoadmap(roadmap);

    // Submit to Backend API using REAL id/slug from the backend profession object
    setSubmitting(true);
    try {
      await userService.submitOnboarding({
        profession_id: targetProf.id,         // real UUID from GET /professions
        profession_slug: targetProf.slug,     // real slug from GET /professions
        assessment_score: targetProf.confidence || 85,
        ai_match_percentage: targetProf.confidence || 85,
        daily_study_time: dailyStudyTime,
        experience_level: experienceLevel,
      });

      // Clear wizard localStorage now that onboarding is saved to DB
      onboardingService.clearProfile();

    } catch (err) {
      console.error('Failed to sync onboarding with backend:', err);
      setSubmitError(
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        'Failed to save your selection. You can still continue — we will retry on your next login.'
      );
    } finally {
      setSubmitting(false);
    }

    setStage('roadmap');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Complete Onboarding & Navigate to Dashboard
  const handleFinishOnboarding = () => {
    navigate('/dashboard');
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'var(--bg-dark)',
        color: 'var(--text-main)',
        padding: '2rem 1rem',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}
    >
      {/* Top Header & Branding */}
      <div style={{ width: '100%', maxWidth: '840px', marginBottom: '2rem', textAlign: 'center' }}>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.375rem 1rem',
            borderRadius: 'var(--radius-full)',
            background: 'var(--primary-light)',
            border: '1px solid var(--primary-glow)',
            color: 'var(--primary)',
            fontWeight: 700,
            fontSize: '0.8125rem',
            marginBottom: '1rem',
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
          }}
        >
          <Sparkles size={16} /> AI Personalized Onboarding
        </div>
        <h1 style={{ fontFamily: 'var(--font-heading)', fontSize: '2.25rem', fontWeight: 800 }}>
          {stage === 'profile' && `Complete Your Profile (Step ${currentStep} of ${totalProfileSteps})`}
          {stage === 'assessment' && 'Career Alignment Assessment'}
          {stage === 'recommendation' && 'Your AI Recommended Career'}
          {stage === 'roadmap' && 'Your Personalized Learning Roadmap'}
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', marginTop: '0.5rem' }}>
          {stage === 'profile' && 'Answer a few quick questions so our AI can design your tailored career path.'}
          {stage === 'assessment' && 'Evaluate your technical logic and career preferences in real-time.'}
          {stage === 'recommendation' && 'Based on your profile and skills assessment, here is your optimal career match.'}
          {stage === 'roadmap' && 'Explore your customized milestone journey designed for maximum career impact.'}
        </p>

        {/* Global Onboarding Stage Stepper Bar */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginTop: '2rem',
            padding: '0.75rem 1.25rem',
            background: 'var(--bg-card)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          {[
            { key: 'profile', label: '1. Profile Wizard' },
            { key: 'assessment', label: '2. Assessment' },
            { key: 'recommendation', label: '3. AI Recommendation' },
            { key: 'roadmap', label: '4. Roadmap' },
          ].map((stg, idx) => {
            const isCurrent = stage === stg.key;
            const isCompleted =
              (stg.key === 'profile' && stage !== 'profile') ||
              (stg.key === 'assessment' && (stage === 'recommendation' || stage === 'roadmap')) ||
              (stg.key === 'recommendation' && stage === 'roadmap');

            return (
              <div
                key={stg.key}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  fontSize: '0.85rem',
                  fontWeight: isCurrent ? 700 : 500,
                  color: isCurrent
                    ? 'var(--primary)'
                    : isCompleted
                    ? 'var(--accent-emerald)'
                    : 'var(--text-dim)',
                }}
              >
                {isCompleted ? (
                  <CheckCircle2 size={18} style={{ color: 'var(--accent-emerald)' }} />
                ) : (
                  <div
                    style={{
                      width: '22px',
                      height: '22px',
                      borderRadius: '50%',
                      background: isCurrent ? 'var(--primary)' : 'var(--bg-input)',
                      color: isCurrent ? '#fff' : 'var(--text-dim)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                    }}
                  >
                    {idx + 1}
                  </div>
                )}
                <span>{stg.label}</span>
              </div>
            );
          })}
        </div>

        {/* Step Progress Bar (For Profile Stage) */}
        {stage === 'profile' && (
          <div
            style={{
              width: '100%',
              height: '6px',
              background: 'rgba(255,255,255,0.06)',
              borderRadius: '3px',
              marginTop: '1rem',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: `${(currentStep / totalProfileSteps) * 100}%`,
                height: '100%',
                background: 'linear-gradient(90deg, var(--primary), var(--secondary))',
                transition: 'width 0.3s ease',
              }}
            />
          </div>
        )}
      </div>

      {/* Main Form Content Container */}
      <div style={{ width: '100%', maxWidth: '840px' }}>
        {/* ================================================================= */}
        {/* STAGE 1: COMPLETE PROFILE WIZARD (STEPS 1 TO 9)                   */}
        {/* ================================================================= */}
        {stage === 'profile' && (
          <Card>
            {/* STEP 1: Personal Details & Education */}
            {currentStep === 1 && (
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.25rem', color: 'var(--text-main)' }}>
                  Step 1: Personal & Education Details
                </h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
                  Tell us about your background and academic status.
                </p>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
                  <div style={{ gridColumn: 'span 2' }}>
                    <Input
                      label="Full Name"
                      type="text"
                      placeholder="e.g. Alex Morgan"
                      icon={User}
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                    />
                  </div>

                  <Input
                    label="Age"
                    type="number"
                    placeholder="e.g. 21"
                    value={age}
                    onChange={(e) => setAge(e.target.value)}
                  />

                  <Input
                    label="Country"
                    type="text"
                    placeholder="e.g. United States, India, UK"
                    icon={MapPin}
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                  />

                  <div style={{ gridColumn: 'span 2' }}>
                    <Input
                      label="College / University"
                      type="text"
                      placeholder="e.g. Stanford University or Tech Institute"
                      icon={Building}
                      value={college}
                      onChange={(e) => setCollege(e.target.value)}
                    />
                  </div>

                  <Input
                    label="Degree / Major"
                    type="text"
                    placeholder="e.g. B.Tech Computer Science"
                    icon={GraduationCap}
                    value={degree}
                    onChange={(e) => setDegree(e.target.value)}
                  />

                  <Input
                    label="Graduation Year"
                    type="text"
                    placeholder="e.g. 2026"
                    icon={Calendar}
                    value={graduationYear}
                    onChange={(e) => setGraduationYear(e.target.value)}
                  />
                </div>
              </div>
            )}

            {/* STEP 2: Career Goal — populated from real backend professions */}
            {currentStep === 2 && (
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                  Step 2: What is your Target Career Goal?
                </h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
                  Select the profession you aspire to master.
                </p>

                {/* Loading state */}
                {professionsLoading && (
                  <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    <div style={{ marginBottom: '0.75rem', fontSize: '1.5rem' }}>⏳</div>
                    Loading professions from server...
                  </div>
                )}

                {/* Error state */}
                {professionsError && !professionsLoading && (
                  <div
                    style={{
                      padding: '1rem',
                      borderRadius: 'var(--radius-md)',
                      background: 'rgba(239, 68, 68, 0.1)',
                      border: '1px solid rgba(239, 68, 68, 0.3)',
                      color: '#fca5a5',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.75rem',
                    }}
                  >
                    <AlertCircle size={20} />
                    <span>{professionsError}</span>
                  </div>
                )}

                {/* Real profession list from backend */}
                {!professionsLoading && !professionsError && (
                  <div className="grid-2" style={{ maxHeight: '420px', overflowY: 'auto', paddingRight: '0.5rem' }}>
                    {backendProfessions.length === 0 ? (
                      <div style={{ gridColumn: 'span 2', textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>
                        No professions available yet. Please contact an administrator.
                      </div>
                    ) : (
                      backendProfessions.map((prof) => {
                        const isSelected = careerGoal === prof.name;
                        return (
                          <div
                            key={prof.id}
                            onClick={() => setCareerGoal(prof.name)}
                            style={{
                              padding: '1rem',
                              borderRadius: 'var(--radius-md)',
                              background: isSelected ? 'var(--primary-light)' : 'var(--bg-input)',
                              border: isSelected ? '2px solid var(--primary)' : '1px solid var(--border-subtle)',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              transition: 'all 0.2s ease',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                              <Briefcase size={20} style={{ color: isSelected ? 'var(--primary)' : 'var(--text-dim)' }} />
                              <div>
                                <span style={{ fontWeight: 600, fontSize: '0.9375rem', color: isSelected ? '#fff' : 'var(--text-main)', display: 'block' }}>
                                  {prof.name}
                                </span>
                                {prof.category && (
                                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                    {prof.category}
                                  </span>
                                )}
                              </div>
                            </div>
                            {isSelected && <CheckCircle2 size={18} style={{ color: 'var(--primary)' }} />}
                          </div>
                        );
                      })
                    )}
                  </div>
                )}
              </div>
            )}

            {/* STEP 3: Experience Level */}
            {currentStep === 3 && (
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                  Step 3: What is your Current Experience Level?
                </h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
                  Choose the option that best reflects your current coding & tech exposure.
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {[
                    {
                      level: 'Beginner',
                      title: 'Beginner (0 - 1 years)',
                      desc: 'Just starting out or learning foundational concepts, syntax, and problem-solving.',
                      icon: BookOpen,
                    },
                    {
                      level: 'Intermediate',
                      title: 'Intermediate (1 - 3 years)',
                      desc: 'Comfortable with programming basics, web/data projects, and looking to specialize.',
                      icon: Code2,
                    },
                    {
                      level: 'Advanced',
                      title: 'Advanced (3+ years)',
                      desc: 'Experienced builder seeking deep architectural mastery, MLOps, or complex system design.',
                      icon: Layers,
                    },
                  ].map((item) => {
                    const isSelected = experienceLevel === item.level;
                    const IconComp = item.icon;
                    return (
                      <div
                        key={item.level}
                        onClick={() => setExperienceLevel(item.level)}
                        style={{
                          padding: '1.25rem',
                          borderRadius: 'var(--radius-md)',
                          background: isSelected ? 'var(--primary-light)' : 'var(--bg-input)',
                          border: isSelected ? '2px solid var(--primary)' : '1px solid var(--border-subtle)',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: '1rem',
                          transition: 'all 0.2s ease',
                        }}
                      >
                        <div
                          style={{
                            padding: '0.625rem',
                            borderRadius: 'var(--radius-sm)',
                            background: isSelected ? 'var(--primary)' : 'rgba(255,255,255,0.05)',
                            color: isSelected ? '#fff' : 'var(--text-dim)',
                          }}
                        >
                          <IconComp size={22} />
                        </div>
                        <div style={{ flex: 1 }}>
                          <h4 style={{ fontWeight: 700, fontSize: '1rem', color: isSelected ? '#fff' : 'var(--text-main)' }}>
                            {item.title}
                          </h4>
                          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                            {item.desc}
                          </p>
                        </div>
                        {isSelected && <CheckCircle2 size={20} style={{ color: 'var(--primary)' }} />}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* STEP 4: Current Skills */}
            {currentStep === 4 && (
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                  Step 4: Select Your Current Skills
                </h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
                  Choose all tools and languages you have worked with (Multi-select).
                </p>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
                  {SKILL_OPTIONS.map((skill) => {
                    const isSelected = selectedSkills.includes(skill);
                    return (
                      <button
                        key={skill}
                        type="button"
                        onClick={() => toggleSkill(skill)}
                        style={{
                          padding: '0.625rem 1.125rem',
                          borderRadius: 'var(--radius-full)',
                          background: isSelected ? 'var(--primary)' : 'var(--bg-input)',
                          color: isSelected ? '#fff' : 'var(--text-main)',
                          border: isSelected ? '1px solid var(--primary-hover)' : '1px solid var(--border-subtle)',
                          fontWeight: 600,
                          fontSize: '0.875rem',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.375rem',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        {isSelected && <Check size={14} />}
                        {skill}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* STEP 5: Interests */}
            {currentStep === 5 && (
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                  Step 5: Choose Your Domain Interests
                </h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
                  Select tech domains you are passionate about exploring (Multi-select).
                </p>

                <div className="grid-2">
                  {INTEREST_OPTIONS.map((item) => {
                    const isSelected = selectedInterests.includes(item.label);
                    return (
                      <div
                        key={item.label}
                        onClick={() => toggleInterest(item.label)}
                        style={{
                          padding: '1rem',
                          borderRadius: 'var(--radius-md)',
                          background: isSelected ? 'var(--primary-light)' : 'var(--bg-input)',
                          border: isSelected ? '2px solid var(--primary)' : '1px solid var(--border-subtle)',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          transition: 'all 0.2s ease',
                        }}
                      >
                        <div>
                          <h5 style={{ fontWeight: 700, fontSize: '0.9375rem', color: isSelected ? '#fff' : 'var(--text-main)' }}>
                            {item.label}
                          </h5>
                          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.125rem' }}>
                            {item.desc}
                          </p>
                        </div>
                        {isSelected && <CheckCircle2 size={18} style={{ color: 'var(--primary)' }} />}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* STEP 6: Daily Study Time */}
            {currentStep === 6 && (
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                  Step 6: Daily Learning Commitment
                </h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
                  How much time can you realistically dedicate to studying each day?
                </p>

                <div className="grid-2">
                  {['30 minutes', '1 hour', '2 hours', '3+ hours'].map((timeOption) => {
                    const isSelected = dailyStudyTime === timeOption;
                    return (
                      <div
                        key={timeOption}
                        onClick={() => setDailyStudyTime(timeOption)}
                        style={{
                          padding: '1.25rem',
                          borderRadius: 'var(--radius-md)',
                          background: isSelected ? 'var(--primary-light)' : 'var(--bg-input)',
                          border: isSelected ? '2px solid var(--primary)' : '1px solid var(--border-subtle)',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '1rem',
                        }}
                      >
                        <Clock size={22} style={{ color: isSelected ? 'var(--primary)' : 'var(--text-dim)' }} />
                        <span style={{ fontWeight: 700, fontSize: '1rem', color: isSelected ? '#fff' : 'var(--text-main)' }}>
                          {timeOption} / day
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* STEP 7: Preferred Learning Style */}
            {currentStep === 7 && (
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                  Step 7: Preferred Learning Style
                </h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
                  How do you absorb complex tech concepts most effectively?
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {[
                    { style: 'Video', desc: 'Visual tutorials, video lectures & interactive walkthroughs' },
                    { style: 'Reading', desc: 'In-depth documentation, technical guides & book chapters' },
                    { style: 'Projects', desc: 'Hands-on building, capstone projects & real codebase work' },
                    { style: 'Practice', desc: 'Interactive coding challenges, drills & quizzes' },
                    { style: 'Mixed', desc: 'Balanced combination of videos, projects & practice' },
                  ].map((item) => {
                    const isSelected = learningStyle === item.style;
                    return (
                      <div
                        key={item.style}
                        onClick={() => setLearningStyle(item.style)}
                        style={{
                          padding: '1rem 1.25rem',
                          borderRadius: 'var(--radius-md)',
                          background: isSelected ? 'var(--primary-light)' : 'var(--bg-input)',
                          border: isSelected ? '2px solid var(--primary)' : '1px solid var(--border-subtle)',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                        }}
                      >
                        <div>
                          <span style={{ fontWeight: 700, fontSize: '0.9375rem', color: isSelected ? '#fff' : 'var(--text-main)' }}>
                            {item.style}
                          </span>
                          <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.125rem' }}>
                            {item.desc}
                          </p>
                        </div>
                        {isSelected && <CheckCircle2 size={18} style={{ color: 'var(--primary)' }} />}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* STEP 8: Primary Goal */}
            {currentStep === 8 && (
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                  Step 8: What is Your Primary Outcome Goal?
                </h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
                  What milestone are you aiming to achieve upon roadmap completion?
                </p>

                <div className="grid-2">
                  {['Internship', 'Placement', 'Job', 'Freelancing', 'Higher Studies'].map((goalOption) => {
                    const isSelected = primaryGoal === goalOption;
                    return (
                      <div
                        key={goalOption}
                        onClick={() => setPrimaryGoal(goalOption)}
                        style={{
                          padding: '1.25rem',
                          borderRadius: 'var(--radius-md)',
                          background: isSelected ? 'var(--primary-light)' : 'var(--bg-input)',
                          border: isSelected ? '2px solid var(--primary)' : '1px solid var(--border-subtle)',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '1rem',
                        }}
                      >
                        <Target size={22} style={{ color: isSelected ? 'var(--primary)' : 'var(--text-dim)' }} />
                        <span style={{ fontWeight: 700, fontSize: '1rem', color: isSelected ? '#fff' : 'var(--text-main)' }}>
                          {goalOption}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* STEP 9: Difficulty Preference */}
            {currentStep === 9 && (
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                  Step 9: Roadmap Difficulty Preference
                </h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
                  Choose how demanding you want your curriculum pace and task difficulty to be.
                </p>

                <div className="grid-2">
                  {[
                    { level: 'Easy', desc: 'Gentle step-by-step guidance with extra practice hints' },
                    { level: 'Medium', desc: 'Balanced industry pace with moderate practical challenges' },
                    { level: 'Hard', desc: 'Accelerated high-intensity pace for rapid career growth' },
                    { level: 'Adaptive', desc: 'AI dynamically calibrates difficulty based on your quiz performance' },
                  ].map((diff) => {
                    const isSelected = difficultyPreference === diff.level;
                    return (
                      <div
                        key={diff.level}
                        onClick={() => setDifficultyPreference(diff.level)}
                        style={{
                          padding: '1.25rem',
                          borderRadius: 'var(--radius-md)',
                          background: isSelected ? 'var(--primary-light)' : 'var(--bg-input)',
                          border: isSelected ? '2px solid var(--primary)' : '1px solid var(--border-subtle)',
                          cursor: 'pointer',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.375rem' }}>
                          <span style={{ fontWeight: 700, fontSize: '1rem', color: isSelected ? '#fff' : 'var(--text-main)' }}>
                            {diff.level}
                          </span>
                          {isSelected && <CheckCircle2 size={18} style={{ color: 'var(--primary)' }} />}
                        </div>
                        <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                          {diff.desc}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Wizard Navigation Controls */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginTop: '2rem',
                paddingTop: '1.25rem',
                borderTop: '1px solid var(--border-subtle)',
              }}
            >
              <Button
                variant="outline"
                onClick={handlePrevStep}
                disabled={currentStep === 1}
                icon={ArrowLeft}
              >
                Previous
              </Button>

              <Button
                variant="primary"
                onClick={handleNextStep}
                icon={currentStep === totalProfileSteps ? Sparkles : ArrowRight}
                disabled={
                  // Block on Step 2 if professions haven't loaded yet
                  (currentStep === 2 && professionsLoading) ||
                  (currentStep === 2 && !professionsError && backendProfessions.length > 0 && !careerGoal)
                }
              >
                {currentStep === totalProfileSteps ? 'Start Career Assessment' : 'Next Step'}
              </Button>
            </div>
          </Card>
        )}

        {/* ================================================================= */}
        {/* STAGE 2: CAREER ASSESSMENT                                        */}
        {/* ================================================================= */}
        {stage === 'assessment' && (
          <Card>
            <div style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--primary)', letterSpacing: '0.05em' }}>
                  QUESTION {assessmentIndex + 1} OF {ASSESSMENT_QUESTIONS.length}
                </span>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '0.25rem' }}>
                  {ASSESSMENT_QUESTIONS[assessmentIndex].question}
                </h3>
              </div>
              <BrainCircuit size={28} style={{ color: 'var(--primary)' }} />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {ASSESSMENT_QUESTIONS[assessmentIndex].options.map((opt, oIdx) => {
                const qId = ASSESSMENT_QUESTIONS[assessmentIndex].id;
                const isSelected = assessmentAnswers[qId]?.text === opt.text;
                return (
                  <div
                    key={oIdx}
                    onClick={() => handleSelectAssessmentOption(qId, opt)}
                    style={{
                      padding: '1.25rem',
                      borderRadius: 'var(--radius-md)',
                      background: isSelected ? 'var(--primary-light)' : 'var(--bg-input)',
                      border: isSelected ? '2px solid var(--primary)' : '1px solid var(--border-subtle)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    <span style={{ fontSize: '0.9375rem', fontWeight: 500, lineHeight: 1.5, color: isSelected ? '#fff' : 'var(--text-main)' }}>
                      {opt.text}
                    </span>
                    {isSelected && <CheckCircle2 size={20} style={{ color: 'var(--primary)', flexShrink: 0 }} />}
                  </div>
                );
              })}
            </div>

            <div style={{ marginTop: '2rem', display: 'flex', justifyContent: 'flex-end' }}>
              <Button
                variant="primary"
                onClick={handleNextAssessment}
                disabled={!assessmentAnswers[ASSESSMENT_QUESTIONS[assessmentIndex].id]}
                icon={ArrowRight}
              >
                {assessmentIndex === ASSESSMENT_QUESTIONS.length - 1 ? 'Analyze & Recommend Career' : 'Next Question'}
              </Button>
            </div>
          </Card>
        )}

        {/* ================================================================= */}
        {/* STAGE 3: PROFESSION RECOMMENDATION (backend data)                 */}
        {/* ================================================================= */}
        {stage === 'recommendation' && recommendationResult && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {/* Primary Recommended Career Card */}
            <Card style={{ border: '2px solid var(--primary)', background: 'linear-gradient(135deg, rgba(15,23,42,0.9) 0%, rgba(99,102,241,0.15) 100%)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                  <div
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.375rem',
                      padding: '0.25rem 0.75rem',
                      borderRadius: 'var(--radius-full)',
                      background: 'rgba(16, 185, 129, 0.2)',
                      color: 'var(--accent-emerald)',
                      fontWeight: 800,
                      fontSize: '0.8125rem',
                      marginBottom: '0.75rem',
                    }}
                  >
                    <Flame size={16} /> #1 TOP RECOMMENDED CAREER
                  </div>
                  <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-main)' }}>
                    {recommendationResult.primary.title}
                  </h2>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.9375rem', marginTop: '0.375rem', maxWidth: '600px' }}>
                    {recommendationResult.primary.description}
                  </p>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <div
                    style={{
                      fontSize: '2.5rem',
                      fontWeight: 900,
                      color: 'var(--accent-emerald)',
                      fontFamily: 'var(--font-heading)',
                      lineHeight: 1,
                    }}
                  >
                    {recommendationResult.primary.confidence}%
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600 }}>MATCH CONFIDENCE</span>
                </div>
              </div>

              {/* Specs Grid */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                  gap: '1rem',
                  margin: '1.5rem 0',
                  padding: '1rem',
                  background: 'rgba(0,0,0,0.25)',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', display: 'block' }}>Category</span>
                  <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-main)' }}>{recommendationResult.primary.category}</span>
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', display: 'block' }}>Est. Duration</span>
                  <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-main)' }}>{recommendationResult.primary.estimatedDuration}</span>
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', display: 'block' }}>Avg. Salary</span>
                  <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--accent-emerald)' }}>{recommendationResult.primary.averageSalary}</span>
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', display: 'block' }}>Job Growth</span>
                  <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--primary)' }}>{recommendationResult.primary.growthRate}</span>
                </div>
              </div>

              {/* Key Required Skills */}
              <div>
                <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--text-muted)', display: 'block', marginBottom: '0.5rem' }}>
                  CORE SKILLS YOU WILL MASTER:
                </span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                  {(recommendationResult.primary.skills || []).map((sk) => (
                    <span
                      key={sk}
                      style={{
                        padding: '0.25rem 0.75rem',
                        borderRadius: 'var(--radius-sm)',
                        background: 'var(--primary-light)',
                        border: '1px solid var(--primary-glow)',
                        color: 'var(--primary)',
                        fontSize: '0.8125rem',
                        fontWeight: 600,
                      }}
                    >
                      {sk}
                    </span>
                  ))}
                </div>
              </div>

              <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'flex-end' }}>
                <Button
                  variant="primary"
                  size="lg"
                  icon={ArrowRight}
                  onClick={() => handleConfirmProfession(recommendationResult.primary)}
                  disabled={submitting}
                >
                  {submitting ? 'Saving...' : 'Accept & Build Roadmap'}
                </Button>
              </div>
            </Card>

            {/* Alternative Career Recommendations */}
            {recommendationResult.alternatives?.length > 0 && (
              <div>
                <h3 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '1rem', color: 'var(--text-main)' }}>
                  Alternative Career Matches
                </h3>
                <div className="grid-3">
                  {recommendationResult.alternatives.map((alt) => (
                    <Card key={alt.id} style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-dim)' }}>{alt.category}</span>
                          <span style={{ fontSize: '0.875rem', fontWeight: 800, color: 'var(--primary)' }}>{alt.confidence}% Match</span>
                        </div>
                        <h4 style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
                          {alt.title}
                        </h4>
                        <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', lineHeight: 1.4, marginBottom: '1rem' }}>
                          {(alt.description || '').substring(0, 100)}{alt.description?.length > 100 ? '...' : ''}
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleConfirmProfession(alt)}
                        style={{ width: '100%' }}
                        disabled={submitting}
                      >
                        Select This Career
                      </Button>
                    </Card>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ================================================================= */}
        {/* STAGE 4: PERSONALIZED ROADMAP PREVIEW                             */}
        {/* ================================================================= */}
        {stage === 'roadmap' && generatedRoadmap && (
          <Card>
            {/* Backend submission error — non-blocking */}
            {submitError && (
              <div
                style={{
                  marginBottom: '1.25rem',
                  padding: '0.875rem 1rem',
                  borderRadius: 'var(--radius-md)',
                  background: 'rgba(234, 179, 8, 0.1)',
                  border: '1px solid rgba(234, 179, 8, 0.3)',
                  color: '#fde68a',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '0.75rem',
                  fontSize: '0.875rem',
                }}
              >
                <AlertCircle size={18} style={{ flexShrink: 0, marginTop: '1px' }} />
                <span><strong>Note:</strong> {submitError}</span>
              </div>
            )}

            <div style={{ marginBottom: '1.5rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--accent-emerald)', letterSpacing: '0.05em' }}>
                    ROADMAP GENERATED SUCCESSFULLY
                  </span>
                  <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)', marginTop: '0.25rem' }}>
                    {generatedRoadmap.title}
                  </h2>
                </div>

                <div style={{ display: 'flex', gap: '1rem' }}>
                  <div style={{ textAlign: 'center', padding: '0.5rem 1rem', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', display: 'block' }}>Duration</span>
                    <span style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--primary)' }}>{generatedRoadmap.estimatedDuration}</span>
                  </div>
                  <div style={{ textAlign: 'center', padding: '0.5rem 1rem', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', display: 'block' }}>Commitment</span>
                    <span style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--secondary)' }}>{generatedRoadmap.dailyCommitment} / day</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Milestones Breakdown */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {generatedRoadmap.milestones.map((m, idx) => (
                <div
                  key={m.id}
                  style={{
                    padding: '1.25rem',
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border-subtle)',
                    position: 'relative',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <div
                        style={{
                          width: '28px',
                          height: '28px',
                          borderRadius: '50%',
                          background: idx === 0 ? 'var(--primary)' : 'rgba(255,255,255,0.08)',
                          color: '#fff',
                          fontWeight: 800,
                          fontSize: '0.875rem',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        {idx + 1}
                      </div>
                      <h4 style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text-main)' }}>{m.title}</h4>
                    </div>
                    <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-muted)' }}>{m.duration}</span>
                  </div>

                  <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                    {m.description}
                  </p>

                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
                    {m.topics.map((topic, tIdx) => (
                      <span
                        key={tIdx}
                        style={{
                          fontSize: '0.75rem',
                          padding: '0.2rem 0.5rem',
                          borderRadius: 'var(--radius-sm)',
                          background: 'rgba(255,255,255,0.04)',
                          border: '1px solid var(--border-subtle)',
                          color: 'var(--text-muted)',
                        }}
                      >
                        • {topic}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Launch Dashboard Action */}
            <div style={{ marginTop: '2rem', display: 'flex', justifyContent: 'flex-end' }}>
              <Button variant="primary" size="lg" icon={ArrowRight} onClick={handleFinishOnboarding}>
                Go to Dashboard
              </Button>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
};

export default OnboardingPage;
