import api from './api';

const userService = {
  submitOnboarding: async (onboardingData) => {
    const response = await api.post('/users/onboarding', onboardingData);
    return response.data;
  },

  getProfile: async () => {
    const response = await api.get('/auth/me');
    return response.data;
  },
};

export default userService;
