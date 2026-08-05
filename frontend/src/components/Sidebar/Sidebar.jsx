import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Compass,
  Map,
  CheckSquare,
  Video,
  TrendingUp,
  Bell,
  User,
  Sparkles,
  Award,
  Zap,
} from 'lucide-react';
import useAuth from '../../hooks/useAuth';

export const Sidebar = ({ isOpen, unreadCount = 0 }) => {
  const { user } = useAuth();

  const userName = user?.full_name || 'Kartik Patidar';
  const initials = userName
    .split(' ')
    .map((n) => n[0])
    .join('')
    .substring(0, 2)
    .toUpperCase();

  const navSections = [
    {
      sectionTitle: 'CAREER PATHWAY',
      items: [
        { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
        { label: 'Professions Catalog', path: '/professions', icon: Compass },
        { label: 'Interactive Roadmap', path: '/roadmaps', icon: Map },
        { label: 'Daily Tasks Hub', path: '/tasks', icon: CheckSquare },
      ],
    },
    {
      sectionTitle: 'AI STUDIO & ANALYTICS',
      items: [
        { label: '1-on-1 AI Interview Room', path: '/interviews', icon: Video, isHot: true },
        { label: 'LeetCode Career Progress', path: '/progress', icon: TrendingUp },
      ],
    },
    {
      sectionTitle: 'ACCOUNT',
      items: [
        { label: 'Notifications Hub', path: '/notifications', icon: Bell, badge: unreadCount },
        { label: 'Candidate Profile', path: '/profile', icon: User },
      ],
    },
  ];

  return (
    <aside className={`sidebar-container ${isOpen ? 'open' : ''}`}>
      {/* BRAND HEADER */}
      <NavLink to="/dashboard" className="sidebar-logo">
        <div className="sidebar-logo-icon">
          <Sparkles size={20} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span style={{ fontSize: '1.15rem', fontWeight: 900, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
            AI Career OS
          </span>
          <span style={{ fontSize: '0.6875rem', fontWeight: 700, color: 'var(--primary)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            Career Learning Engine
          </span>
        </div>
      </NavLink>

      {/* GROUPED NAVIGATION LIST */}
      <nav className="sidebar-nav">
        {navSections.map((sec, secIdx) => (
          <div key={secIdx} className="sidebar-section">
            <span className="sidebar-section-title">{sec.sectionTitle}</span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', marginTop: '0.35rem' }}>
              {sec.items.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
                  >
                    <Icon size={19} className="sidebar-link-icon" />
                    <span style={{ flex: 1 }}>{item.label}</span>
                    {item.isHot && <span className="badge-pill badge-amber" style={{ fontSize: '0.65rem', padding: '0.1rem 0.4rem' }}>LIVE</span>}
                    {Boolean(item.badge) && <span className="sidebar-badge">{item.badge}</span>}
                  </NavLink>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* SIDEBAR FOOTER CANDIDATE PROFILE CARD */}
      <div className="sidebar-footer">
        <div className="sidebar-candidate-card">
          <div className="candidate-avatar-frame">
            <span>{initials}</span>
            <span className="status-online-dot" />
          </div>
          <div style={{ overflow: 'hidden' }}>
            <h5 className="candidate-card-name">{userName}</h5>
            <span className="candidate-card-role">Machine Learning Engineer</span>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;

