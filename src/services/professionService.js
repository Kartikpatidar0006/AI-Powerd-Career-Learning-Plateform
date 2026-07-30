import api from './api';
import { ENDPOINTS } from '../constants/apiEndpoints';

const professionService = {
  getProfessions: async (params = {}) => {
    const response = await api.get(ENDPOINTS.PROFESSIONS, { params });
    return response.data;
  },

  getProfessionBySlug: async (slug) => {
    const response = await api.get(`${ENDPOINTS.PROFESSIONS}/slug/${slug}`);
    return response.data;
  },

  getProfessionById: async (id) => {
    const response = await api.get(`${ENDPOINTS.PROFESSIONS}/${id}`);
    return response.data;
  },
};

export default professionService;
