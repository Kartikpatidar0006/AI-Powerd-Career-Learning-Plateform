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
} from 'lucide-react';

export const Sidebar = ({ isOpen, unreadCount = 0 }) => {
  const navItems = [
    { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { label: 'Professions', path: '/professions', icon: Compass },
    { label: 'Roadmaps', path: '/roadmaps', icon: Map },
    { label: 'Tasks', path: '/tasks', icon: CheckSquare },
    { label: 'Mock Interviews', path: '/interviews', icon: Video },
    { label: 'My Progress', path: '/progress', icon: TrendingUp },
    { label: 'Notifications', path: '/notifications', icon: Bell, badge: unreadCount },
    { label: 'Profile', path: '/profile', icon: User },
  ];

  return (
    <aside className={`sidebar-container ${isOpen ? 'open' : ''}`}>
      <NavLink to="/dashboard" className="sidebar-logo">
        <div className="sidebar-logo-icon">AI</div>
        <span>CareerPlatform</span>
      </NavLink>

      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            >
              <Icon size={20} />
              <span>{item.label}</span>
              {Boolean(item.badge) && <span className="sidebar-badge">{item.badge}</span>}
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
};

export default Sidebar;
