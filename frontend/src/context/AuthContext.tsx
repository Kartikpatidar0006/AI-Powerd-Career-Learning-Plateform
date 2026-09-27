/**
 * Authentication context provider.
 *
 * Manages auth state globally: JWT tokens, current user, and
 * authentication status. Persists tokens to localStorage and
 * auto-loads the user profile on mount if tokens exist.
 */

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from 'react';
import type { User, AuthState, LoginCredentials, SignupCredentials } from '../types/auth';
import * as authService from '../services/auth';

interface AuthContextValue extends AuthState {
  login: (credentials: LoginCredentials) => Promise<void>;
  signup: (credentials: SignupCredentials) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(
    () => localStorage.getItem('access_token')
  );
  const [refreshToken, setRefreshToken] = useState<string | null>(
    () => localStorage.getItem('refresh_token')
  );
  const [isLoading, setIsLoading] = useState<boolean>(true);

  /**
   * Persist tokens to localStorage and state.
   */
  const storeTokens = useCallback((access: string, refresh: string) => {
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
    setAccessToken(access);
    setRefreshToken(refresh);
  }, []);

  /**
   * Clear all auth state and tokens.
   */
  const clearAuth = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setAccessToken(null);
    setRefreshToken(null);
    setUser(null);
  }, []);

  /**
   * Load the current user profile using the stored access token.
   */
  const loadUser = useCallback(async () => {
    try {
      const currentUser = await authService.getCurrentUser();
      setUser(currentUser);
    } catch {
      clearAuth();
    }
  }, [clearAuth]);

  /**
   * On mount, attempt to load the user if we have a stored token.
   */
  useEffect(() => {
    const init = async () => {
      if (accessToken) {
        await loadUser();
      }
      setIsLoading(false);
    };
    init();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * Log in with email and password.
   */
  const login = useCallback(async (credentials: LoginCredentials) => {
    const tokens = await authService.login(credentials);
    storeTokens(tokens.access_token, tokens.refresh_token);
    const currentUser = await authService.getCurrentUser();
    setUser(currentUser);
  }, [storeTokens]);

  /**
   * Register a new account, then automatically log in.
   */
  const signup = useCallback(async (credentials: SignupCredentials) => {
    await authService.signup(credentials);
    // Auto-login after successful signup
    await login(credentials);
  }, [login]);

  /**
   * Log out — revoke refresh token on server, then clear local state.
   */
  const logout = useCallback(async () => {
    await authService.logout(refreshToken);
    clearAuth();
  }, [clearAuth, refreshToken]);

  const value: AuthContextValue = {
    user,
    accessToken,
    refreshToken,
    isAuthenticated: !!user && !!accessToken,
    isLoading,
    login,
    signup,
    logout,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Hook to access auth context. Must be used within AuthProvider.
 */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
