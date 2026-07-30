import api from './api';
import { ENDPOINTS } from '../constants/apiEndpoints';

const dashboardService = {
  getStudentDashboard: async () => {
    const response = await api.get(ENDPOINTS.STUDENT_DASHBOARD);
    return response.data;
  },
};

export default dashboardService;
