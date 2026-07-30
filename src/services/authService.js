import api from './api';
import { ENDPOINTS } from '../constants/apiEndpoints';

const authService = {
  login: async (credentials) => {
    const response = await api.post(ENDPOINTS.LOGIN, {
      email: credentials.email,
      password: credentials.password,
    });
    return response.data;
  },

  register: async (userData) => {
    const response = await api.post(ENDPOINTS.REGISTER, {
      full_name: userData.full_name,
      email: userData.email,
      password: userData.password,
    });
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
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
  },
};

export default authService;
