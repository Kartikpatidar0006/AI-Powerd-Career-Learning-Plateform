import api from './api';
import { ENDPOINTS } from '../constants/apiEndpoints';

const roadmapService = {
  getCareerRoadmaps: async (params = {}) => {
    const response = await api.get(ENDPOINTS.ROADMAPS, { params });
    return response.data;
  },

  getRoadmapById: async (roadmapId) => {
    const response = await api.get(`${ENDPOINTS.ROADMAPS}/${roadmapId}`);
    return response.data;
  },

  getRoadmapSteps: async (params = {}) => {
    const response = await api.get(ENDPOINTS.ROADMAP_STEPS, { params });
    return response.data;
  },
};

export default roadmapService;
