export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';

export const ENDPOINTS = {
  // Auth
  LOGIN: '/auth/login',
  REGISTER: '/auth/register',
  REFRESH: '/auth/refresh',
  ME: '/auth/me',
  CHANGE_PASSWORD: '/auth/change-password',

  // User & Dashboard
  STUDENT_DASHBOARD: '/dashboard/student',
  MY_DASHBOARD: '/dashboard/me',

  // Professions & Skills
  PROFESSIONS: '/professions',
  SKILLS: '/skills',

  // Roadmaps & Steps
  ROADMAPS: '/career-roadmaps',
  ROADMAP_STEPS: '/roadmap-steps',

  // Tasks & Submissions
  TASKS: '/tasks',
  SUBMISSIONS: '/tasks/my-submissions',
  SUBMIT_TASK: (taskId) => `/tasks/${taskId}/submit`,
  EVALUATE_SUBMISSION: (submissionId) => `/submissions/${submissionId}/evaluate`,
  SUBMISSION_FEEDBACK: (submissionId) => `/submissions/${submissionId}/feedback`,

  // Mock Interviews
  INTERVIEWS: '/interviews',
  MY_INTERVIEWS: '/interviews/me',
  SCHEDULE_INTERVIEW: (taskId) => `/interviews/schedule/${taskId}`,
  START_INTERVIEW: (interviewId) => `/interviews/${interviewId}/start`,
  INTERVIEW_QUESTIONS: (interviewId) => `/interviews/${interviewId}/questions`,
  ANSWER_QUESTION: (questionId) => `/interviews/questions/${questionId}/answer`,
  FINISH_INTERVIEW: (interviewId) => `/interviews/${interviewId}/finish`,
  EVALUATE_INTERVIEW: (interviewId) => `/interviews/${interviewId}/evaluate`,
  INTERVIEW_FEEDBACK: (interviewId) => `/interviews/${interviewId}/feedback`,
  MY_INTERVIEW_FEEDBACK: '/users/me/interview-feedback',

  // Progress & Notifications
  USER_PROGRESS: '/user-progress',
  MY_PROGRESS: '/users/me/progress',
  ROADMAP_PROGRESS: (roadmapId) => `/roadmaps/${roadmapId}/progress`,
  NOTIFICATIONS: '/notifications/me',
  MY_NOTIFICATIONS: '/users/me/notifications',
  MARK_NOTIF_READ: (notifId) => `/notifications/${notifId}/read`,
};
