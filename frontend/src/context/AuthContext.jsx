import React, { createContext, useState, useEffect, useCallback } from 'react';
import authService from '../services/authService';
import api from '../services/api';
import { ENDPOINTS } from '../constants/apiEndpoints';
import toast from 'react-hot-toast';

export const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem('user');
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });

  const [token, setToken] = useState(() => {
    return localStorage.getItem('token') || localStorage.getItem('access_token');
  });

  const [loading, setLoading] = useState(true);

  /**
   * Try to refresh the access token using the stored refresh token.
   * Returns the new access token on success, or null on failure.
   */
  const tryRefreshToken = useCallback(async () => {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) return null;

    try {
      const response = await api.post(ENDPOINTS.REFRESH, {
        refresh_token: refreshToken,
      });
      const newAccessToken = response.data?.access_token;
      if (newAccessToken) {
        localStorage.setItem('token', newAccessToken);
        localStorage.setItem('access_token', newAccessToken);
        return newAccessToken;
      }
      return null;
    } catch {
      return null;
    }
  }, []);

  const restoreSession = useCallback(async () => {
    const storedToken = localStorage.getItem('token') || localStorage.getItem('access_token');

    if (!storedToken) {
      setUser(null);
      setToken(null);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const userData = await authService.getMe();
      setUser(userData);
      setToken(storedToken);
      localStorage.setItem('user', JSON.stringify(userData));
    } catch (error) {
      // Access token might be expired — try refreshing it
      const newToken = await tryRefreshToken();
      if (newToken) {
        try {
          const userData = await authService.getMe();
          setUser(userData);
          setToken(newToken);
          localStorage.setItem('user', JSON.stringify(userData));
          return; // Session restored successfully via refresh
        } catch {
          // Refresh token also failed — full logout
        }
      }
      authService.logout();
      setUser(null);
      setToken(null);
    } finally {
      setLoading(false);
    }
  }, [tryRefreshToken]);

  useEffect(() => {
    restoreSession();
  }, [restoreSession]);

  /**
   * Helper to save tokens and fetch user data — shared by login & register.
   */
  const _saveTokensAndLoadUser = async (tokenData) => {
    const accessToken = tokenData.access_token || tokenData.token;

    if (!accessToken) {
      throw new Error('Access token was not returned by server.');
    }

    localStorage.setItem('token', accessToken);
    localStorage.setItem('access_token', accessToken);
    if (tokenData.refresh_token) {
      localStorage.setItem('refresh_token', tokenData.refresh_token);
    }
    setToken(accessToken);

    const userData = await authService.getMe();
    setUser(userData);
    localStorage.setItem('user', JSON.stringify(userData));
    return userData;
  };

  const login = async (credentials) => {
    try {
      setLoading(true);
      const tokenData = await authService.login(credentials);
      const userData = await _saveTokensAndLoadUser(tokenData);

      toast.success(`Welcome back, ${userData.full_name || 'User'}!`);
      return userData;
    } catch (error) {
      const errorMessage =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        'Invalid email or password. Please try again.';
      toast.error(errorMessage);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const register = async (userData) => {
    try {
      setLoading(true);
      const tokenData = await authService.register(userData);

      // Auto-login: save the tokens and load user profile
      const userProfile = await _saveTokensAndLoadUser(tokenData);

      toast.success(`Welcome, ${userProfile.full_name || 'User'}! Your account has been created.`);
      return userProfile;
    } catch (error) {
      const errorMessage =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        'Registration failed. Please check input values.';
      toast.error(errorMessage);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    authService.logout();
    setUser(null);
    setToken(null);
    toast.success('Logged out successfully.');
  };

  const value = {
    user,
    token,
    loading,
    isAuthenticated: Boolean(token && user),
    login,
    register,
    logout,
    restoreSession,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
