import api from './api';
import { ENDPOINTS } from '../constants/apiEndpoints';

const authService = {
  login: async (credentials) => {
    // FastAPI OAuth2 password request form or JSON payload
    const response = await api.post(ENDPOINTS.LOGIN, credentials);
    return response.data;
  },

  register: async (userData) => {
    const response = await api.post(ENDPOINTS.REGISTER, userData);
    return response.data;
  },

  getMe: async () => {
    const response = await api.get(ENDPOINTS.ME);
    return response.data;
  },

  changePassword: async (passwordData) => {
    const response = await api.post(ENDPOINTS.CHANGE_PASSWORD, passwordData);
    return response.data;
  },

  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
  },
};

export default authService;
