import api from './api';
import { ENDPOINTS } from '../constants/apiEndpoints';

const progressService = {
  getUserOverallProgress: async () => {
    const response = await api.get(ENDPOINTS.MY_PROGRESS);
    return response.data;
  },

  getRoadmapProgress: async (roadmapId) => {
    const response = await api.get(ENDPOINTS.ROADMAP_PROGRESS(roadmapId));
    return response.data;
  },

  getUserSkillProgress: async (params = {}) => {
    const response = await api.get(ENDPOINTS.USER_PROGRESS, { params });
    return response.data;
  },
};

export default progressService;
