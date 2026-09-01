const ONBOARDING_STORAGE_KEY = 'ai_career_onboarding_profile';

export const onboardingService = {
  /**
   * Save user's onboarding wizard inputs to local storage (wizard progress only).
   * Never store profession/roadmap data that must come from the DB.
   */
  saveProfile: (profileData) => {
    try {
      const existing = onboardingService.getProfile() || {};
      const updated = { ...existing, ...profileData, updatedAt: new Date().toISOString() };
      localStorage.setItem(ONBOARDING_STORAGE_KEY, JSON.stringify(updated));
      return updated;
    } catch (e) {
      console.error('Failed to save onboarding profile', e);
      return profileData;
    }
  },

  /**
   * Get user's onboarding wizard progress from local storage.
   */
  getProfile: () => {
    try {
      const data = localStorage.getItem(ONBOARDING_STORAGE_KEY);
      return data ? JSON.parse(data) : null;
    } catch (e) {
      return null;
    }
  },

  /**
   * Clear onboarding wizard progress from local storage.
   * Call this after onboarding is successfully submitted to the backend.
   */
  clearProfile: () => {
    try {
      localStorage.removeItem(ONBOARDING_STORAGE_KEY);
    } catch (e) {
      // ignore
    }
  },

  /**
   * Score and rank backend professions against the user's profile + assessment answers.
   * All profession objects come from the real API — IDs and slugs are always backend-sourced.
   *
   * @param {object} profile - Saved onboarding wizard answers
   * @param {Array}  assessmentAnswers - Array of selected assessment option objects
   * @param {Array}  backendProfessions - Professions fetched from GET /professions
   * @returns {{ primary, alternatives, allRanked, calculatedAt }}
   */
  rankProfessions: (profile, assessmentAnswers = [], backendProfessions = []) => {
    if (!backendProfessions.length) return null;

    const scores = {};

    // Initialize every backend profession with a baseline score
    backendProfessions.forEach((prof) => {
      scores[prof.id] = 50;
    });

    // 1. Direct career goal alignment — match by name (case-insensitive)
    if (profile?.careerGoal) {
      backendProfessions.forEach((prof) => {
        if (
          prof.name?.toLowerCase().includes(profile.careerGoal.toLowerCase()) ||
          profile.careerGoal.toLowerCase().includes(prof.name?.toLowerCase())
        ) {
          scores[prof.id] += 30;
        }
      });
    }

    // 2. Skill match boost — compare user skills against profession required_skills
    const userSkills = profile?.skills || [];
    if (userSkills.length > 0) {
      backendProfessions.forEach((prof) => {
        const profSkills = Array.isArray(prof.required_skills) ? prof.required_skills : [];
        const matchingSkills = profSkills.filter((sk) =>
          userSkills.some((uSk) => uSk.toLowerCase() === sk.toLowerCase())
        );
        const matchRatio = matchingSkills.length / Math.max(profSkills.length, 1);
        scores[prof.id] += Math.round(matchRatio * 20);
      });
    }

    // 3. Interest alignment boost — match user interests against profession category
    const userInterests = profile?.interests || [];
    if (userInterests.length > 0) {
      backendProfessions.forEach((prof) => {
        const catLower = (prof.category || '').toLowerCase();
        userInterests.forEach((interest) => {
          const intLower = interest.toLowerCase();
          if (
            (intLower.includes('ai') && (catLower.includes('ai') || catLower.includes('machine'))) ||
            (intLower.includes('web') && catLower.includes('software')) ||
            (intLower.includes('frontend') && catLower.includes('software')) ||
            (intLower.includes('data') && catLower.includes('data')) ||
            (intLower.includes('cloud') && catLower.includes('cloud')) ||
            (intLower.includes('security') && catLower.includes('security'))
          ) {
            scores[prof.id] += 8;
          }
        });
      });
    }

    // 4. Assessment answer alignment boost — options carry alignment hints (profession names)
    assessmentAnswers.forEach((answer) => {
      if (answer?.alignment) {
        answer.alignment.forEach((alignedName) => {
          backendProfessions.forEach((prof) => {
            if (
              prof.name?.toLowerCase().includes(alignedName.toLowerCase()) ||
              alignedName.toLowerCase().includes(prof.name?.toLowerCase())
            ) {
              scores[prof.id] += 12;
            }
          });
        });
      }
    });

    // Normalize scores to realistic confidence percentages (68% – 98%)
    const maxRawScore = Math.max(...Object.values(scores), 1);

    const allRanked = backendProfessions
      .map((prof) => {
        const raw = scores[prof.id] || 50;
        const confidence = Math.min(98, Math.max(68, Math.round((raw / maxRawScore) * 95)));
        // Normalize field names so the rest of the UI stays the same
        return {
          // Real backend fields (used for API submission)
          id: prof.id,
          slug: prof.slug,
          // Display fields mapped from backend schema
          title: prof.name,
          name: prof.name,
          category: prof.category || 'Technology',
          description: prof.description || '',
          skills: Array.isArray(prof.required_skills) ? prof.required_skills : [],
          estimatedDuration: prof.estimated_duration || '12-16 Weeks',
          averageSalary: prof.average_salary
            ? `$${Number(prof.average_salary).toLocaleString()}`
            : 'Market Rate',
          growthRate: prof.growth_rate ? `+${prof.growth_rate}% annual growth` : 'Growing',
          // Scoring
          confidence,
          rawScore: raw,
        };
      })
      .sort((a, b) => b.confidence - a.confidence);

    return {
      primary: allRanked[0],
      alternatives: allRanked.slice(1, 4),
      allRanked,
      calculatedAt: new Date().toISOString(),
    };
  },

  /**
   * Generate a local preview roadmap (for the onboarding roadmap stage only).
   * Uses real profession data from the backend — profession.id and profession.slug
   * are always sourced from the API response, never from local constants.
   *
   * @param {object} profession - Backend-sourced profession object (with real id/slug)
   * @param {object} profile    - Saved wizard profile answers
   */
  generateRoadmap: (profession, profile) => {
    const studyTime = profile?.dailyStudyTime || '1 hour';
    const level = profile?.experienceLevel || 'Beginner';

    const milestones = [
      {
        id: 'm1',
        title: 'Phase 1: Core Foundations & Prerequisites',
        description: `Master fundamental ${profession.title} concepts, core syntax, and essential development tooling.`,
        duration: 'Weeks 1-4',
        skills: profession.skills.slice(0, 3),
        status: 'In Progress',
        progressPercent: 0,
        topics: [
          'Environment Setup & CLI Tools',
          'Core Programming Logic & Syntax',
          'Version Control with Git & GitHub',
          'Basic Data Structures & Problem Solving',
        ],
      },
      {
        id: 'm2',
        title: 'Phase 2: Applied Architecture & Frameworks',
        description: `Build real-world ${profession.title} modules, integrate APIs, and implement system patterns.`,
        duration: 'Weeks 5-8',
        skills: profession.skills.slice(2, 5),
        status: 'Upcoming',
        progressPercent: 0,
        topics: [
          'Framework Setup & API Integration',
          'Database Querying & Data Persistence',
          'Modular Architecture & Design Patterns',
          'Unit Testing & Code Quality Audits',
        ],
      },
      {
        id: 'm3',
        title: 'Phase 3: Advanced Projects & Production Systems',
        description: `Deploy end-to-end applications, optimize performance, and implement cloud/AI integrations.`,
        duration: 'Weeks 9-12',
        skills: profession.skills.slice(4),
        status: 'Upcoming',
        progressPercent: 0,
        topics: [
          'Containerization & Deployment Pipelines',
          'Performance Tuning & Monitoring',
          'Capstone Portfolio Project Implementation',
          'Security & Scalability Best Practices',
        ],
      },
      {
        id: 'm4',
        title: 'Phase 4: Career Readiness & AI Mock Interviews',
        description: `Refine your resume, prepare for technical system design interviews, and complete AI mock sessions.`,
        duration: 'Weeks 13-16',
        skills: ['System Design', 'Interviewing', 'Portfolio Review'],
        status: 'Upcoming',
        progressPercent: 0,
        topics: [
          'Technical Resume & Portfolio Polishing',
          'AI Mock Interview Simulations',
          'System Design & Problem Solving Drills',
          'Job Application Strategy & Placement',
        ],
      },
    ];

    return {
      title: `${profession.title} Personalized Career Roadmap`,
      professionName: profession.title,
      professionId: profession.id,        // real backend UUID
      professionSlug: profession.slug,    // real backend slug
      estimatedDuration: profession.estimatedDuration,
      dailyCommitment: studyTime,
      userLevel: level,
      milestones,
      generatedAt: new Date().toISOString(),
    };
  },
};

export default onboardingService;
