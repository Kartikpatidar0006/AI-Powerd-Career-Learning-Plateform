import { PROFESSION_CATALOG } from '../constants/professionCatalog';

const ONBOARDING_STORAGE_KEY = 'ai_career_onboarding_profile';
const RECOMMENDATION_STORAGE_KEY = 'ai_career_recommendation';

export const onboardingService = {
  /**
   * Save user's onboarding wizard inputs to local storage
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
   * Get user's onboarding profile from local storage
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
   * Calculate career recommendations based on wizard profile + assessment answers
   */
  calculateRecommendation: (profile, assessmentAnswers = []) => {
    const scores = {};

    // Initialize scores for all catalog items
    PROFESSION_CATALOG.forEach((prof) => {
      scores[prof.name] = 50; // base baseline score
    });

    // 1. Direct Goal Alignment boost
    if (profile?.careerGoal && scores[profile.careerGoal] !== undefined) {
      scores[profile.careerGoal] += 30;
    }

    // 2. Skill match boost
    const userSkills = profile?.skills || [];
    if (userSkills.length > 0) {
      PROFESSION_CATALOG.forEach((prof) => {
        const matchingSkills = prof.skills.filter((sk) =>
          userSkills.some((uSk) => uSk.toLowerCase() === sk.toLowerCase())
        );
        const matchRatio = matchingSkills.length / Math.max(prof.skills.length, 1);
        scores[prof.name] += Math.round(matchRatio * 20);
      });
    }

    // 3. Interest alignment boost
    const userInterests = profile?.interests || [];
    if (userInterests.length > 0) {
      PROFESSION_CATALOG.forEach((prof) => {
        userInterests.forEach((interest) => {
          if (
            (interest.toLowerCase().includes('ai') && prof.category.includes('AI')) ||
            (interest.toLowerCase().includes('web') && prof.category.includes('Software')) ||
            (interest.toLowerCase().includes('data') && prof.category.includes('Data')) ||
            (interest.toLowerCase().includes('cloud') && prof.category.includes('Cloud')) ||
            (interest.toLowerCase().includes('security') && prof.category.includes('Security'))
          ) {
            scores[prof.name] += 8;
          }
        });
      });
    }

    // 4. Assessment Answer alignment boost
    assessmentAnswers.forEach((answer) => {
      if (answer?.alignment) {
        answer.alignment.forEach((profName) => {
          if (scores[profName] !== undefined) {
            scores[profName] += 12;
          }
        });
      }
    });

    // Rank and normalize scores into percentages (max 98%, min 65%)
    const maxRawScore = Math.max(...Object.values(scores), 1);
    
    const rankedProfessions = PROFESSION_CATALOG.map((prof) => {
      const raw = scores[prof.name] || 50;
      // Normalization formula to yield realistic confidence percentages (75% to 96%)
      const confidence = Math.min(98, Math.max(68, Math.round((raw / maxRawScore) * 95)));
      return {
        ...prof,
        confidence,
        rawScore: raw,
      };
    }).sort((a, b) => b.confidence - a.confidence);

    const primaryRecommendation = rankedProfessions[0];
    const alternatives = rankedProfessions.slice(1, 4);

    const result = {
      primary: primaryRecommendation,
      alternatives,
      allRanked: rankedProfessions,
      calculatedAt: new Date().toISOString(),
    };

    try {
      localStorage.setItem(RECOMMENDATION_STORAGE_KEY, JSON.stringify(result));
    } catch (e) {
      // ignore
    }

    return result;
  },

  /**
   * Get calculated recommendation from storage
   */
  getRecommendation: () => {
    try {
      const data = localStorage.getItem(RECOMMENDATION_STORAGE_KEY);
      return data ? JSON.parse(data) : null;
    } catch (e) {
      return null;
    }
  },

  /**
   * Generate customized roadmap based on selected/recommended profession and profile metrics
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
      professionId: profession.id,
      estimatedDuration: profession.estimatedDuration,
      dailyCommitment: studyTime,
      userLevel: level,
      milestones,
      generatedAt: new Date().toISOString(),
    };
  },
};

export default onboardingService;
