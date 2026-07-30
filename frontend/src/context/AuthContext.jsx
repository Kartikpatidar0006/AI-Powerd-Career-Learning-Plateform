import React, { createContext, useState, useEffect, useCallback } from 'react';
import authService from '../services/authService';
import toast from 'react-hot-toast';

export const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem('token') || localStorage.getItem('access_token'));
  const [loading, setLoading] = useState(true);

  const restoreSession = useCallback(async () => {
    const storedToken = localStorage.getItem('token') || localStorage.getItem('access_token');
    if (!storedToken) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const userData = await authService.getMe();
      setUser(userData);
      setToken(storedToken);
    } catch (error) {
      authService.logout();
      setUser(null);
      setToken(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    restoreSession();
  }, [restoreSession]);

  const login = async (credentials) => {
    try {
      setLoading(true);
      const data = await authService.login(credentials);
      const authToken = data.access_token || data.token;
      
      localStorage.setItem('token', authToken);
      setToken(authToken);

      const userData = await authService.getMe();
      setUser(userData);
      localStorage.setItem('user', JSON.stringify(userData));

      toast.success('Welcome back!');
      return userData;
    } catch (error) {
      const message = error.response?.data?.detail || 'Login failed. Please check credentials.';
      toast.error(message);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const register = async (userData) => {
    try {
      setLoading(true);
      const response = await authService.register(userData);
      toast.success('Registration successful! Please login to continue.');
      return response;
    } catch (error) {
      const message = error.response?.data?.detail || 'Registration failed. Please try again.';
      toast.error(message);
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
