/**
 * AppNavbar — Shared navigation bar for authenticated pages.
 *
 * Provides consistent navigation across Dashboard, Roadmap, Tasks, and History.
 * Highlights the current active route.
 */

import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function AppNavbar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  const navLinks = [
    { path: '/dashboard', label: 'Dashboard', id: 'nav-dashboard' },
    { path: '/roadmap', label: 'Roadmap', id: 'nav-roadmap' },
    { path: '/tasks', label: '⚡ Daily Task', id: 'nav-tasks' },
    { path: '/history', label: 'History', id: 'nav-history' },
  ];

  return (
    <nav className="border-b border-surface-700/30 bg-surface-900/40 backdrop-blur-xl sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 py-3.5 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-primary-500/15 border border-primary-400/20 flex items-center justify-center">
            <svg className="w-5 h-5 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.636 50.636 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342M6.75 15a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm0 0v-3.675A55.378 55.378 0 0 1 12 8.443m-7.007 11.55A5.981 5.981 0 0 0 6.75 15.75v-1.5" />
            </svg>
          </div>
          <span className="font-semibold text-surface-50 tracking-tight text-sm">Career Platform</span>
        </div>

        {/* Nav links */}
        <div className="hidden md:flex items-center gap-1">
          {navLinks.map((link) => {
            const isActive = location.pathname === link.path;
            return (
              <button
                key={link.path}
                id={link.id}
                onClick={() => navigate(link.path)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
                  isActive
                    ? 'bg-primary-500/15 text-primary-300 border border-primary-500/25'
                    : 'text-surface-300 hover:text-surface-100 hover:bg-surface-800/60'
                }`}
              >
                {link.label}
              </button>
            );
          })}
        </div>

        {/* User info + logout */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-surface-200/70 hidden sm:block">{user?.email}</span>
          <button
            onClick={handleLogout}
            id="navbar-logout"
            className="px-3.5 py-1.5 text-xs font-medium text-surface-200 bg-surface-800/60 hover:bg-surface-700/60 border border-surface-700/40 rounded-xl transition cursor-pointer"
          >
            Sign out
          </button>
        </div>
      </div>
    </nav>
  );
}
