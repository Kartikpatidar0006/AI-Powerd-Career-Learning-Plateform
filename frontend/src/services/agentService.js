/**
 * frontend/src/services/agentService.js
 * API calls for all 5 AI Agents
 */
import api from './api';

const AGENT_BASE = 'http://127.0.0.1:8005/api/v1';

// Helper: direct axios call to agent service
const agentApi = (method, path, data) =>
  api[method](`${AGENT_BASE}${path}`, data);

// ─── Agent 1: Student Onboarding ─────────────────────────────────────────
export const onboardStudent = (data) => agentApi('post', '/students', data);
export const getStudent = (studentId) => agentApi('get', `/students/${studentId}`);
export const updateStudent = (studentId, data) => agentApi('patch', `/students/${studentId}`, data);
export const getStudentDashboard = (studentId) => agentApi('get', `/students/${studentId}/dashboard`);

// ─── Agent 2: Problem Generation ─────────────────────────────────────────
export const generateProblems = (data) => agentApi('post', '/problems/generate', data);
export const getStudentProblems = (studentId) => agentApi('get', `/problems/student/${studentId}`);
export const assignProblem = (data) => agentApi('post', '/problems/assign', data);

// ─── Agent 3: GitHub Evaluation ──────────────────────────────────────────
export const evaluateSubmission = (data) => agentApi('post', '/evaluations', data);
export const getEvaluation = (evaluationId) => agentApi('get', `/evaluations/${evaluationId}`);
export const getStudentEvaluations = (studentId) => agentApi('get', `/evaluations/student/${studentId}`);

// ─── Agent 4: AI Interview ────────────────────────────────────────────────
export const startInterview = (data) => agentApi('post', '/interviews/start', data);
export const getCurrentQuestion = (interviewId) => agentApi('get', `/interviews/${interviewId}/question`);
export const submitAnswer = (data) => agentApi('post', '/interviews/answer', data);
export const getInterview = (interviewId) => agentApi('get', `/interviews/${interviewId}`);
export const getStudentInterviews = (studentId) => agentApi('get', `/interviews/student/${studentId}`);

// ─── Agent 5: Career Guidance ─────────────────────────────────────────────
export const generateGuidance = (studentId, interviewId = null) =>
  agentApi('post', `/guidance/${studentId}${interviewId ? `?interview_id=${interviewId}` : ''}`);
export const getLatestGuidance = (studentId) => agentApi('get', `/guidance/${studentId}/latest`);
export const getGuidanceHistory = (studentId) => agentApi('get', `/guidance/${studentId}/history`);
