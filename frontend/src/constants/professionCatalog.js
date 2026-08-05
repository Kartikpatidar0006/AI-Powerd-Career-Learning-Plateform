/**
 * Complete catalog of professional career paths in tech.
 * Restricted to the 2 primary featured tracks:
 * 1. Machine Learning Engineer
 * 2. Frontend Developer / Engineer
 */

export const PROFESSION_CATALOG = [
  {
    id: 'ml-engineer',
    slug: 'machine-learning-engineer',
    title: 'Machine Learning Engineer',
    name: 'Machine Learning Engineer',
    category: 'AI & Machine Learning',
    description: 'Develop predictive models, feature pipelines, recommendation engines, and end-to-end MLOps production systems.',
    skills: ['Python', 'Scikit-learn', 'PyTorch', 'Pandas', 'NumPy', 'Docker', 'SQL'],
    estimatedDuration: '16 Weeks',
    difficulty: 'Advanced',
    averageSalary: '$130,000 - $175,000',
    growthRate: '+32% annual growth',
    badgeColor: '#8b5cf6',
    icon: 'Cpu',
  },
  {
    id: 'frontend-developer',
    slug: 'frontend-developer',
    title: 'Frontend Developer',
    name: 'Frontend Developer',
    category: 'Software Engineering',
    description: 'Build responsive, accessible, interactive web interfaces using React, JavaScript, modern CSS, and component systems.',
    skills: ['JavaScript', 'React', 'Git', 'Node.js', 'CSS'],
    estimatedDuration: '12 Weeks',
    difficulty: 'Intermediate',
    averageSalary: '$100,000 - $140,000',
    growthRate: '+20% annual growth',
    badgeColor: '#6366f1',
    icon: 'Layout',
  },
];

export const SKILL_OPTIONS = [
  'Python',
  'JavaScript',
  'React',
  'Node.js',
  'SQL',
  'Git',
  'Linux',
  'Docker',
  'PyTorch',
  'Pandas',
  'NumPy',
  'Scikit-learn',
  'CSS',
];

export const INTEREST_OPTIONS = [
  { label: 'AI & Machine Learning', icon: 'Cpu', desc: 'Predictive Models, Neural Networks & MLOps' },
  { label: 'Frontend & UI Engineering', icon: 'Layout', desc: 'Modern Web Apps, React & User Interfaces' },
];

export const GOAL_PROFESSION_OPTIONS = [
  'Machine Learning Engineer',
  'Frontend Developer',
];

export const ASSESSMENT_QUESTIONS = [
  {
    id: 1,
    question: 'Which area of problem-solving excites you the most?',
    options: [
      { text: 'Developing predictive models, feature pipelines, and machine learning algorithms', alignment: ['Machine Learning Engineer'] },
      { text: 'Building responsive web interfaces, interactive components, and user-facing features', alignment: ['Frontend Developer'] },
    ],
  },
  {
    id: 2,
    question: 'What is your ideal project artifact?',
    options: [
      { text: 'A trained machine learning model with feature engineering and MLOps deployment', alignment: ['Machine Learning Engineer'] },
      { text: 'A modern, responsive React web application with clean component styling', alignment: ['Frontend Developer'] },
    ],
  },
  {
    id: 3,
    question: 'What type of daily coding activity sounds most rewarding to you?',
    options: [
      { text: 'Optimizing model hyper-parameters and feature transformations using Pandas, Scikit-Learn & PyTorch', alignment: ['Machine Learning Engineer'] },
      { text: 'Creating reusable React components, state management hooks, and UI micro-animations', alignment: ['Frontend Developer'] },
    ],
  },
];

