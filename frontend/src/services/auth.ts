/**
 * Auth service — API calls for authentication operations.
 *
 * All auth-related HTTP calls go through this module.
 * Business logic stays here, components just consume the results.
 */

import apiClient from './api';
import type { LoginCredentials, SignupCredentials, TokenResponse, User } from '../types/auth';

/**
 * Register a new user account.
 */
export async function signup(credentials: SignupCredentials): Promise<User> {
  const response = await apiClient.post<User>('/auth/signup', credentials);
  return response.data;
}

/**
 * Authenticate with email and password, returns JWT tokens.
 */
export async function login(credentials: LoginCredentials): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>('/auth/login', credentials);
  return response.data;
}

/**
 * Refresh the access token using a valid refresh token.
 */
export async function refreshToken(refresh_token: string): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>('/auth/refresh-token', {
    refresh_token,
  });
  return response.data;
}

/**
 * Get the currently authenticated user's profile.
 */
export async function getCurrentUser(): Promise<User> {
  const response = await apiClient.get<User>('/auth/me');
  return response.data;
}

/**
 * Logout — revoke the refresh token on the server.
 */
export async function logout(refresh_token: string | null): Promise<void> {
  try {
    await apiClient.post('/auth/logout', {
      refresh_token,
    });
  } catch {
    // Swallow errors — we clear local state regardless
  }
}

