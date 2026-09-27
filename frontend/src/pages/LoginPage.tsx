/**
 * Login page — authenticates users with email and password.
 */

import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import type { AxiosError } from 'axios';
import type { ApiError } from '../types/auth';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      await login({ email, password });
      navigate('/dashboard', { replace: true });
    } catch (err) {
      const axiosError = err as AxiosError<ApiError>;
      setError(
        axiosError.response?.data?.detail || 'Login failed. Please try again.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      {/* Background decoration */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full bg-primary-500/10 blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 rounded-full bg-accent-500/8 blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Logo/Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-primary-500/15 border border-primary-400/20 mb-4">
            <svg className="w-7 h-7 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.636 50.636 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342M6.75 15a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm0 0v-3.675A55.378 55.378 0 0 1 12 8.443m-7.007 11.55A5.981 5.981 0 0 0 6.75 15.75v-1.5" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-surface-50 tracking-tight">
            Welcome back
          </h1>
          <p className="text-surface-200/70 text-sm mt-1">
            Sign in to your Career Platform account
          </p>
        </div>

        {/* Card */}
        <div className="bg-surface-900/60 backdrop-blur-xl border border-surface-700/40 rounded-2xl p-8 shadow-2xl shadow-black/20">
          <form onSubmit={handleSubmit} className="space-y-5" id="login-form">
            {/* Error banner */}
            {error && (
              <div className="bg-danger-500/10 border border-danger-400/20 rounded-xl px-4 py-3 text-danger-400 text-sm" role="alert" id="login-error">
                {error}
              </div>
            )}

            {/* Email */}
            <div>
              <label htmlFor="login-email" className="block text-sm font-medium text-surface-200 mb-1.5">
                Email
              </label>
              <input
                id="login-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                autoComplete="email"
                className="w-full px-4 py-2.5 bg-surface-800/60 border border-surface-700/50 rounded-xl text-surface-50 placeholder:text-surface-200/40 focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400/50 transition-all duration-200"
              />
            </div>

            {/* Password */}
            <div>
              <label htmlFor="login-password" className="block text-sm font-medium text-surface-200 mb-1.5">
                Password
              </label>
              <input
                id="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                autoComplete="current-password"
                className="w-full px-4 py-2.5 bg-surface-800/60 border border-surface-700/50 rounded-xl text-surface-50 placeholder:text-surface-200/40 focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400/50 transition-all duration-200"
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isSubmitting}
              id="login-submit"
              className="w-full py-2.5 bg-primary-500 hover:bg-primary-400 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all duration-200 cursor-pointer shadow-lg shadow-primary-500/20 hover:shadow-primary-400/30"
            >
              {isSubmitting ? (
                <span className="inline-flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Signing in...
                </span>
              ) : (
                'Sign in'
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="my-6 border-t border-surface-700/30" />

          {/* Link to signup */}
          <p className="text-center text-sm text-surface-200/60">
            Don't have an account?{' '}
            <Link
              to="/signup"
              className="text-primary-400 hover:text-primary-300 font-medium transition-colors"
              id="login-signup-link"
            >
              Create one
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
