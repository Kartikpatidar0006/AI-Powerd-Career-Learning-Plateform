/**
 * Dashboard page — protected route showing authenticated user info.
 *
 * This is a placeholder that will be expanded in future weeks.
 * Currently shows the user's profile and a logout button.
 */

import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

export default function DashboardPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Navigation bar */}
      <nav className="border-b border-surface-700/30 bg-surface-900/40 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary-500/15 border border-primary-400/20 flex items-center justify-center">
              <svg className="w-5 h-5 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.636 50.636 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342M6.75 15a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm0 0v-3.675A55.378 55.378 0 0 1 12 8.443m-7.007 11.55A5.981 5.981 0 0 0 6.75 15.75v-1.5" />
              </svg>
            </div>
            <span className="font-semibold text-surface-50 tracking-tight">Career Platform</span>
          </div>

          <div className="flex items-center gap-4">
            <span className="text-sm text-surface-200/70 hidden sm:block">{user?.email}</span>
            <button
              onClick={handleLogout}
              id="dashboard-logout"
              className="px-4 py-2 text-sm font-medium text-surface-200 bg-surface-800/60 hover:bg-surface-700/60 border border-surface-700/40 rounded-xl transition-all duration-200 cursor-pointer"
            >
              Sign out
            </button>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-10">
        {/* Welcome section */}
        <div className="mb-10">
          <h1 className="text-3xl font-bold text-surface-50 tracking-tight">
            Welcome back! 👋
          </h1>
          <p className="text-surface-200/60 mt-2">
            Your AI-powered career dashboard is coming soon.
          </p>
        </div>

        {/* Stats grid placeholder */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-10">
          {[
            { label: 'Learning Paths', value: '—', icon: '📚', color: 'primary' },
            { label: 'Skills Tracked', value: '—', icon: '🎯', color: 'accent' },
            { label: 'AI Recommendations', value: '—', icon: '🤖', color: 'primary' },
          ].map((stat) => (
            <div
              key={stat.label}
              className="bg-surface-900/50 backdrop-blur-sm border border-surface-700/30 rounded-2xl p-6 hover:border-surface-700/50 transition-all duration-300"
            >
              <div className="flex items-center justify-between mb-4">
                <span className="text-2xl">{stat.icon}</span>
                <span className="text-xs font-medium text-surface-200/40 uppercase tracking-wider">
                  Coming Soon
                </span>
              </div>
              <p className="text-2xl font-bold text-surface-50">{stat.value}</p>
              <p className="text-sm text-surface-200/50 mt-1">{stat.label}</p>
            </div>
          ))}
        </div>

        {/* User profile card */}
        <div className="bg-surface-900/50 backdrop-blur-sm border border-surface-700/30 rounded-2xl p-6">
          <h2 className="text-lg font-semibold text-surface-50 mb-4">Your Profile</h2>
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <span className="text-sm text-surface-200/50 w-24">Email</span>
              <span className="text-sm text-surface-100 font-mono">{user?.email}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-surface-200/50 w-24">User ID</span>
              <span className="text-sm text-surface-100 font-mono text-xs">{user?.id}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-surface-200/50 w-24">Status</span>
              <span className="inline-flex items-center gap-1.5 text-sm">
                <span className={`w-2 h-2 rounded-full ${user?.is_active ? 'bg-accent-400' : 'bg-danger-400'}`} />
                <span className="text-surface-100">{user?.is_active ? 'Active' : 'Inactive'}</span>
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-surface-200/50 w-24">Joined</span>
              <span className="text-sm text-surface-100">
                {user?.created_at ? new Date(user.created_at).toLocaleDateString('en-US', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                }) : '—'}
              </span>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
