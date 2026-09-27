/**
 * Signup page — register new user accounts.
 */

import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import type { AxiosError } from 'axios';
import type { ApiError } from '../types/auth';

export default function SignupPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { signup } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setIsSubmitting(true);

    try {
      await signup({ email, password });
      navigate('/dashboard', { replace: true });
    } catch (err) {
      const axiosError = err as AxiosError<ApiError>;
      setError(
        axiosError.response?.data?.detail || 'Registration failed. Please try again.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      {/* Background decoration */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 w-96 h-96 rounded-full bg-accent-500/10 blur-3xl" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 rounded-full bg-primary-500/8 blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Logo/Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-accent-500/15 border border-accent-400/20 mb-4">
            <svg className="w-7 h-7 text-accent-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.59 14.37a6 6 0 0 1-5.84 7.38v-4.8m5.84-2.58a14.98 14.98 0 0 0 6.16-12.12A14.98 14.98 0 0 0 9.631 8.41m5.96 5.96a14.926 14.926 0 0 1-5.841 2.58m-.119-8.54a6 6 0 0 0-7.381 5.84h4.8m2.58-5.84a14.927 14.927 0 0 0-2.58 5.84m2.699 2.7c-.103.021-.207.041-.311.06a15.09 15.09 0 0 1-2.448-2.448 14.9 14.9 0 0 1 .06-.312m-2.24 2.39a4.493 4.493 0 0 0-1.757 4.306 4.493 4.493 0 0 0 4.306-1.758M16.5 9a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0Z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-surface-50 tracking-tight">
            Create your account
          </h1>
          <p className="text-surface-200/70 text-sm mt-1">
            Start your AI-powered career journey
          </p>
        </div>

        {/* Card */}
        <div className="bg-surface-900/60 backdrop-blur-xl border border-surface-700/40 rounded-2xl p-8 shadow-2xl shadow-black/20">
          <form onSubmit={handleSubmit} className="space-y-5" id="signup-form">
            {/* Error banner */}
            {error && (
              <div className="bg-danger-500/10 border border-danger-400/20 rounded-xl px-4 py-3 text-danger-400 text-sm" role="alert" id="signup-error">
                {error}
              </div>
            )}

            {/* Email */}
            <div>
              <label htmlFor="signup-email" className="block text-sm font-medium text-surface-200 mb-1.5">
                Email
              </label>
              <input
                id="signup-email"
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
              <label htmlFor="signup-password" className="block text-sm font-medium text-surface-200 mb-1.5">
                Password
              </label>
              <input
                id="signup-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min. 8 characters"
                required
                minLength={8}
                autoComplete="new-password"
                className="w-full px-4 py-2.5 bg-surface-800/60 border border-surface-700/50 rounded-xl text-surface-50 placeholder:text-surface-200/40 focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400/50 transition-all duration-200"
              />
            </div>

            {/* Confirm Password */}
            <div>
              <label htmlFor="signup-confirm-password" className="block text-sm font-medium text-surface-200 mb-1.5">
                Confirm Password
              </label>
              <input
                id="signup-confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter password"
                required
                minLength={8}
                autoComplete="new-password"
                className="w-full px-4 py-2.5 bg-surface-800/60 border border-surface-700/50 rounded-xl text-surface-50 placeholder:text-surface-200/40 focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400/50 transition-all duration-200"
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isSubmitting}
              id="signup-submit"
              className="w-full py-2.5 bg-primary-500 hover:bg-primary-400 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all duration-200 cursor-pointer shadow-lg shadow-primary-500/20 hover:shadow-primary-400/30"
            >
              {isSubmitting ? (
                <span className="inline-flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Creating account...
                </span>
              ) : (
                'Create account'
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="my-6 border-t border-surface-700/30" />

          {/* Link to login */}
          <p className="text-center text-sm text-surface-200/60">
            Already have an account?{' '}
            <Link
              to="/login"
              className="text-primary-400 hover:text-primary-300 font-medium transition-colors"
              id="signup-login-link"
            >
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
