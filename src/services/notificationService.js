import api from './api';
import { ENDPOINTS } from '../constants/apiEndpoints';

const notificationService = {
  getMyNotifications: async (params = {}) => {
    const response = await api.get(ENDPOINTS.NOTIFICATIONS, { params });
    return response.data;
  },

  markAsRead: async (notificationId) => {
    const response = await api.patch(ENDPOINTS.MARK_NOTIF_READ(notificationId));
    return response.data;
  },
};

export default notificationService;
