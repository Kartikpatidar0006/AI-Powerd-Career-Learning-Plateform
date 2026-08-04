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
} from 'lucide-react';
import Card from '../components/Card/Card';
import Button from '../components/Button/Button';
import Input from '../components/Input/Input';
import useAuth from '../hooks/useAuth';
import userService from '../services/userService';
import {
  PROFESSION_CATALOG,
  SKILL_OPTIONS,
  INTEREST_OPTIONS,
  GOAL_PROFESSION_OPTIONS,
  ASSESSMENT_QUESTIONS,
} from '../constants/professionCatalog';
import onboardingService from '../services/onboardingService';

export const OnboardingPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  // Onboarding Stage: 'profile' | 'assessment' | 'recommendation' | 'roadmap'
  const [stage, setStage] = useState('profile');
  const [currentStep, setCurrentStep] = useState(1);
  const totalProfileSteps = 9;

  // Step 1: Personal & Education
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [age, setAge] = useState('');
  const [country, setCountry] = useState('India');
  const [college, setCollege] = useState('');
  const [degree, setDegree] = useState('B.Tech Computer Science');
  const [graduationYear, setGraduationYear] = useState('2026');

  // Step 2: Career Goal
  const [careerGoal, setCareerGoal] = useState('AI Engineer');

  // Step 3: Experience Level
  const [experienceLevel, setExperienceLevel] = useState('Beginner');

  // Step 4: Current Skills
  const [selectedSkills, setSelectedSkills] = useState(['Python', 'JavaScript']);

  // Step 5: Interests
  const [selectedInterests, setSelectedInterests] = useState(['AI', 'Web Development']);

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

  // Calculated Recommendation & Selected Profession
  const [recommendationResult, setRecommendationResult] = useState(null);
  const [chosenProfession, setChosenProfession] = useState(null);
  const [generatedRoadmap, setGeneratedRoadmap] = useState(null);

  // Sync user full name when available
  useEffect(() => {
    if (user?.full_name && !fullName) {
      setFullName(user.full_name);
    }
  }, [user]);

  // Handle skill toggle
  const toggleSkill = (skill) => {
    if (selectedSkills.includes(skill)) {
      setSelectedSkills(selectedSkills.filter((s) => s !== skill));
    } else {
      setSelectedSkills([...selectedSkills, skill]);
    }
  };

  // Handle interest toggle
  const toggleInterest = (interest) => {
    if (selectedInterests.includes(interest)) {
      setSelectedInterests(selectedInterests.filter((i) => i !== interest));
    } else {
      setSelectedInterests([...selectedInterests, interest]);
    }
  };

  // Move to next step in profile wizard
  const handleNextStep = () => {
    if (currentStep < totalProfileSteps) {
      setCurrentStep((prev) => prev + 1);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      // Save Profile & Transition to Assessment
      const profileData = {
        fullName,
        age,
        country,
        college,
        degree,
        graduationYear,
        careerGoal,
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
      // Finish Assessment & Calculate Recommendation
      const profileData = onboardingService.getProfile();
      const answersArray = Object.values(assessmentAnswers);
      const result = onboardingService.calculateRecommendation(profileData, answersArray);
      setRecommendationResult(result);
      setChosenProfession(result.primary);
      setStage('recommendation');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  // Confirm Profession and Generate Roadmap
  const handleConfirmProfession = async (professionToSet) => {
    const targetProf = professionToSet || chosenProfession || recommendationResult?.primary;
    setChosenProfession(targetProf);

    const profileData = onboardingService.getProfile();
    const roadmap = onboardingService.generateRoadmap(targetProf, profileData);
    setGeneratedRoadmap(roadmap);

    // Save profile to local storage as fallback
    onboardingService.saveProfile({
      selectedProfession: targetProf,
      activeRoadmap: roadmap,
      onboardingCompleted: true,
    });

    // Save to Database via Backend API
    try {
      await userService.submitOnboarding({
        profession_id: targetProf.id,
        profession_slug: targetProf.slug,
        assessment_score: targetProf.confidence || 85,
        ai_match_percentage: targetProf.confidence || 85,
        daily_study_time: dailyStudyTime,
        experience_level: experienceLevel,
      });
    } catch (err) {
      console.error('Failed to sync onboarding with backend', err);
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
            justify: 'space-between',
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

            {/* STEP 2: Career Goal */}
            {currentStep === 2 && (
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                  Step 2: What is your Target Career Goal?
                </h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
                  Select the profession you aspire to master.
                </p>

                <div className="grid-2" style={{ maxHeight: '420px', overflowY: 'auto', paddingRight: '0.5rem' }}>
                  {GOAL_PROFESSION_OPTIONS.map((profName) => {
                    const isSelected = careerGoal === profName;
                    return (
                      <div
                        key={profName}
                        onClick={() => setCareerGoal(profName)}
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
                          <span style={{ fontWeight: 600, fontSize: '0.9375rem', color: isSelected ? '#fff' : 'var(--text-main)' }}>
                            {profName}
                          </span>
                        </div>
                        {isSelected && <CheckCircle2 size={18} style={{ color: 'var(--primary)' }} />}
                      </div>
                    );
                  })}
                </div>
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
                justify: 'space-between',
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
        {/* STAGE 3: PROFESSION RECOMMENDATION                                */}
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
                  {recommendationResult.primary.skills.map((sk) => (
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
                >
                  Accept & Build Roadmap
                </Button>
              </div>
            </Card>

            {/* Alternative Career Recommendations */}
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
                        {alt.description.substring(0, 100)}...
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleConfirmProfession(alt)}
                      style={{ width: '100%' }}
                    >
                      Select This Career
                    </Button>
                  </Card>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* STAGE 4: PERSONALIZED ROADMAP PREVIEW                             */}
        {/* ================================================================= */}
        {stage === 'roadmap' && generatedRoadmap && (
          <Card>
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
