import axios from 'axios';
import { API_BASE_URL, ENDPOINTS } from '../constants/apiEndpoints';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Track whether a token refresh is already in progress to prevent duplicate calls.
let isRefreshing = false;
let refreshSubscribers = [];

function onRefreshComplete(newToken) {
  refreshSubscribers.forEach((cb) => cb(newToken));
  refreshSubscribers = [];
}

function addRefreshSubscriber(cb) {
  refreshSubscribers.push(cb);
}

// Request Interceptor: Automatically attach JWT from localStorage
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token') || localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor: Automatically refresh token on 401, then retry
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Only attempt refresh on 401, and not on auth endpoints themselves to avoid loops
    if (
      error.response &&
      error.response.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/login') &&
      !originalRequest.url?.includes('/auth/register') &&
      !originalRequest.url?.includes('/auth/refresh')
    ) {
      originalRequest._retry = true;
      const refreshToken = localStorage.getItem('refresh_token');

      if (refreshToken) {
        if (!isRefreshing) {
          isRefreshing = true;

          try {
            const { data } = await axios.post(
              `${API_BASE_URL}${ENDPOINTS.REFRESH}`,
              { refresh_token: refreshToken },
              { headers: { 'Content-Type': 'application/json' } }
            );

            const newAccessToken = data.access_token;
            localStorage.setItem('token', newAccessToken);
            localStorage.setItem('access_token', newAccessToken);

            isRefreshing = false;
            onRefreshComplete(newAccessToken);

            // Retry the original request with the new token
            originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
            return api(originalRequest);
          } catch {
            isRefreshing = false;
            refreshSubscribers = [];
            // Refresh failed — clear everything and redirect to login
            localStorage.removeItem('token');
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            localStorage.removeItem('user');
            if (!window.location.pathname.includes('/login') && !window.location.pathname.includes('/register')) {
              window.location.href = '/login';
            }
            return Promise.reject(error);
          }
        } else {
          // Another refresh is in progress — queue this request
          return new Promise((resolve) => {
            addRefreshSubscriber((newToken) => {
              originalRequest.headers.Authorization = `Bearer ${newToken}`;
              resolve(api(originalRequest));
            });
          });
        }
      } else {
        // No refresh token available — clear auth and redirect
        localStorage.removeItem('token');
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        if (!window.location.pathname.includes('/login') && !window.location.pathname.includes('/register')) {
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

export default api;
