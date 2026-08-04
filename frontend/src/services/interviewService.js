import api from './api';
import { ENDPOINTS } from '../constants/apiEndpoints';

const interviewService = {
  scheduleInterview: async (taskId) => {
    const response = await api.post(ENDPOINTS.SCHEDULE_INTERVIEW(taskId));
    return response.data;
  },

  getMyInterviews: async (params = {}) => {
    const response = await api.get(ENDPOINTS.MY_INTERVIEWS, { params });
    return response.data;
  },

  getInterviewById: async (interviewId) => {
    const response = await api.get(`${ENDPOINTS.INTERVIEWS}/${interviewId}`);
    return response.data;
  },

  cancelInterview: async (interviewId) => {
    const response = await api.post(`${ENDPOINTS.INTERVIEWS}/${interviewId}/cancel`);
    return response.data;
  },

  startInterview: async (interviewId) => {
    const response = await api.post(ENDPOINTS.START_INTERVIEW(interviewId));
    return response.data;
  },

  getInterviewQuestions: async (interviewId) => {
    const response = await api.get(ENDPOINTS.INTERVIEW_QUESTIONS(interviewId));
    return response.data;
  },

  answerQuestion: async (questionId, answerData) => {
    const response = await api.post(ENDPOINTS.ANSWER_QUESTION(questionId), answerData);
    return response.data;
  },

  finishInterview: async (interviewId) => {
    const response = await api.post(ENDPOINTS.FINISH_INTERVIEW(interviewId));
    return response.data;
  },

  generateFollowup: async (interviewId, questionId, answerText) => {
    const response = await api.post(`/interviews/${interviewId}/followup`, null, {
      params: { question_id: questionId, answer_text: answerText },
    });
    return response.data;
  },

  evaluateInterview: async (interviewId) => {
    const response = await api.post(ENDPOINTS.EVALUATE_INTERVIEW(interviewId));
    return response.data;
  },

  getInterviewFeedback: async (interviewId) => {
    const response = await api.get(ENDPOINTS.INTERVIEW_FEEDBACK(interviewId));
    return response.data;
  },

  getUserInterviewFeedback: async (params = {}) => {
    const response = await api.get(ENDPOINTS.MY_INTERVIEW_FEEDBACK, { params });
    return response.data;
  },
};

export default interviewService;
