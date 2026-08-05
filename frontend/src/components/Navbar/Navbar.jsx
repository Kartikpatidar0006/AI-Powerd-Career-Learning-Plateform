import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Bell, Menu, User, LogOut, Search, Sun } from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '../../hooks/useAuth';
import { getInitials } from '../../utils/formatters';

export const Navbar = ({ onToggleSidebar, unreadCount = 0 }) => {
  const { user, logout } = useAuth();
  const [showDropdown, setShowDropdown] = useState(false);
  const navigate = useNavigate();

  const handleLogout = () => {
    setShowDropdown(false);
    logout();
    navigate('/login');
  };

  return (
    <nav className="navbar-container">
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <button
          onClick={onToggleSidebar}
          style={{ background: 'none', border: 'none', color: 'var(--text-main)', cursor: 'pointer', display: 'flex', padding: '0.25rem' }}
          className="mobile-menu-btn"
          aria-label="Toggle Navigation Sidebar"
        >
          <Menu size={22} />
        </button>
        <div className="search-bar" style={{ position: 'relative', width: '280px' }}>
          <Search size={16} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
          <input
            type="text"
            placeholder="Search tasks, roadmaps, skills..."
            style={{
              width: '100%',
              background: 'var(--bg-input)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-full)',
              padding: '0.4rem 0.875rem 0.4rem 2.2rem',
              color: 'var(--text-main)',
              fontSize: '0.875rem',
              outline: 'none',
            }}
          />
        </div>
      </div>

      <div className="navbar-user-menu">
        {/* Dark / Light Mode Toggle Button */}
        <button
          onClick={() => {
            const isDark = document.body.classList.toggle('dark-theme');
            toast.success(isDark ? '🌙 Dark Mode Activated' : '☀️ Light Mode Activated');
          }}
          className="notif-btn"
          title="Toggle Light/Dark Theme"
          style={{ cursor: 'pointer' }}
        >
          <Sun size={18} className="theme-icon-light" />
        </button>

        <button
          onClick={() => navigate('/notifications')}
          className="notif-btn"
          title="Notifications"
        >
          <Bell size={18} />
          {unreadCount > 0 && <span className="notif-dot" />}
        </button>

        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setShowDropdown(!showDropdown)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.625rem' }}
          >
            <div className="avatar-circle">{getInitials(user?.full_name)}</div>
            <div style={{ textAlign: 'left' }}>
              <p style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-main)', lineHeight: 1.2 }}>
                {user?.full_name || 'Learner Account'}
              </p>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {user?.email || 'authenticated'}
              </p>
            </div>
          </button>

          {showDropdown && (
            <div
              style={{
                position: 'absolute',
                right: 0,
                top: '50px',
                width: '220px',
                background: '#FFFFFF',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                boxShadow: 'var(--shadow-lg)',
                padding: '0.5rem',
                zIndex: 200,
              }}
            >
              <div style={{ padding: '0.5rem 0.875rem', borderBottom: '1px solid var(--border-subtle)', marginBottom: '0.375rem' }}>
                <p style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-main)' }}>{user?.full_name}</p>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user?.email}</p>
              </div>

              <Link
                to="/profile"
                onClick={() => setShowDropdown(false)}
                style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', padding: '0.625rem 0.875rem', color: 'var(--text-main)', textDecoration: 'none', fontSize: '0.875rem', borderRadius: 'var(--radius-sm)' }}
              >
                <User size={16} /> Profile Settings
              </Link>

              <button
                onClick={handleLogout}
                style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '0.625rem', padding: '0.625rem 0.875rem', color: 'var(--accent-rose)', background: 'none', border: 'none', fontSize: '0.875rem', cursor: 'pointer', borderRadius: 'var(--radius-sm)' }}
              >
                <LogOut size={16} /> Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
