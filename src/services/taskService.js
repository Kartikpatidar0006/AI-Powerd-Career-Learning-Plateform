import api from './api';
import { ENDPOINTS } from '../constants/apiEndpoints';

const taskService = {
  getTasks: async (params = {}) => {
    const response = await api.get(ENDPOINTS.TASKS, { params });
    return response.data;
  },

  getTaskById: async (taskId) => {
    const response = await api.get(`${ENDPOINTS.TASKS}/${taskId}`);
    return response.data;
  },

  getTasksByStep: async (roadmapStepId) => {
    const response = await api.get(`${ENDPOINTS.TASKS}/by-step/${roadmapStepId}`);
    return response.data;
  },

  submitTask: async (taskId, submissionData) => {
    const response = await api.post(ENDPOINTS.SUBMIT_TASK(taskId), submissionData);
    return response.data;
  },

  getMySubmissions: async (params = {}) => {
    const response = await api.get(ENDPOINTS.SUBMISSIONS, { params });
    return response.data;
  },

  evaluateSubmission: async (submissionId) => {
    const response = await api.post(ENDPOINTS.EVALUATE_SUBMISSION(submissionId));
    return response.data;
  },

  getSubmissionFeedback: async (submissionId) => {
    const response = await api.get(ENDPOINTS.SUBMISSION_FEEDBACK(submissionId));
    return response.data;
  },
};

export default taskService;
