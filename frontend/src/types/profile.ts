/**
 * Profile and Onboarding TypeScript definitions.
 */

export interface EducationInfo {
  degree: string;
  branch: string;
  year: number;
  institution: string;
}

export type ProficiencyLevel = 'beginner' | 'intermediate' | 'advanced';
export type ExperienceLevel = 'student' | 'fresher' | '1-2yrs' | '2+yrs';

export interface SkillItem {
  skill_name: string;
  category: string;
  proficiency_level: ProficiencyLevel;
  confidence_score: number;
}

export interface DashboardData {
  skill_distribution: Record<string, number>;
  category_averages?: Record<string, number>;
  strongest_areas: string[];
  weakest_areas: string[];
  readiness_score: number;
  readiness_summary: string;
}

export interface StudentProfile {
  id: string;
  user_id: string;
  education: EducationInfo;
  raw_input: {
    education: EducationInfo;
    skills_description: string;
    target_role: string;
    experience_level: ExperienceLevel;
  };
  structured_skills: SkillItem[];
  target_role: string;
  experience_level: ExperienceLevel;
  dashboard_data: DashboardData;
  is_locked: boolean;
  created_at: string;
  updated_at: string;
}

export interface OnboardingFormData {
  education: EducationInfo;
  skills_description: string;
  target_role: string;
  experience_level: ExperienceLevel;
}
