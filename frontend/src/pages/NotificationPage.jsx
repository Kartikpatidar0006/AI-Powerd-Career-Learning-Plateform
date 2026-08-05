import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell,
  Check,
  Info,
  Sparkles,
  Bot,
  Video,
  Code2,
  CheckCircle2,
  Trash2,
  CheckCheck,
  Flame,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react';
import toast from 'react-hot-toast';
import PageHeader from '../components/PageHeader/PageHeader';
import Card from '../components/Card/Card';
import Button from '../components/Button/Button';
import Loader from '../components/Loader/Loader';
import EmptyState from '../components/EmptyState/EmptyState';
import notificationService from '../services/notificationService';
import { formatDateTime } from '../utils/formatters';

export const NotificationPage = () => {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterTab, setFilterTab] = useState('all'); // 'all' | 'unread' | 'task' | 'interview' | 'system'

  const navigate = useNavigate();

  const defaultAiAlerts = [
    {
      id: 'notif-1',
      title: '🤖 Day 1 Task Assigned by AI Learning Agent',
      message: 'The AI Agent evaluated your profile level and assigned "Build Automated ETL Feature Engineering Pipeline".',
      type: 'Task',
      category: 'task',
      is_read: false,
      created_at: new Date().toISOString(),
      actionUrl: '/tasks',
      actionLabel: 'Start Daily Task',
    },
    {
      id: 'notif-2',
      title: '🐙 GitHub AI Code Review Agent Standing By',
      message: 'Paste your GitHub repository link when submitting your solution for instant AI code quality scoring.',
      type: 'Task',
      category: 'task',
      is_read: false,
      created_at: new Date(Date.now() - 3600000).toISOString(),
      actionUrl: '/tasks/1/submit',
      actionLabel: 'Submit GitHub Repo',
    },
    {
      id: 'notif-3',
      title: '🎙️ 1-on-1 AI Video Recruiter Studio Unlocked',
      message: 'Alex Vance (Lead AI Recruiter) is ready for your 1-on-1 technical interview session with real-time speech synthesis.',
      type: 'Interview',
      category: 'interview',
      is_read: false,
      created_at: new Date(Date.now() - 7200000).toISOString(),
      actionUrl: '/interview',
      actionLabel: 'Launch AI Interview',
    },
    {
      id: 'notif-4',
      title: '🔥 Active Study Streak Updated',
      message: 'You have logged activity today. Complete your daily interview session to extend your streak!',
      type: 'System',
      category: 'system',
      is_read: true,
      created_at: new Date(Date.now() - 86400000).toISOString(),
      actionUrl: '/progress',
      actionLabel: 'View Progress Stats',
    },
  ];

  const fetchNotifications = async () => {
    try {
      setLoading(true);
      const data = await notificationService.getMyNotifications();
      const apiItems = Array.isArray(data) ? data : data.items || [];
      setNotifications(apiItems.length > 0 ? apiItems : defaultAiAlerts);
    } catch (err) {
      setNotifications(defaultAiAlerts);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifications();
  }, []);

  const handleMarkAsRead = async (id) => {
    try {
      await notificationService.markAsRead(id);
    } catch {
      // Local fallback mark read
    }
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
    );
    toast.success('Notification marked as read');
  };

  const handleMarkAllAsRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    toast.success('All notifications marked as read');
  };

  const handleClearRead = () => {
    setNotifications((prev) => prev.filter((n) => !n.is_read));
    toast.success('Cleared read notifications');
  };

  // Filtered notifications
  const filteredNotifs = notifications.filter((n) => {
    if (filterTab === 'unread') return !n.is_read;
    if (filterTab === 'task') return (n.type || '').toLowerCase().includes('task') || n.category === 'task';
    if (filterTab === 'interview') return (n.type || '').toLowerCase().includes('interview') || n.category === 'interview';
    if (filterTab === 'system') return (n.type || '').toLowerCase().includes('system') || n.category === 'system';
    return true;
  });

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  if (loading) return <Loader label="Loading AI notifications and alert hub..." />;

  return (
    <div>
      <PageHeader
        title="AI Notification & Alert Hub"
        description="Real-time alerts for daily task assignments, GitHub code reviews, 1-on-1 AI interviews, and streak milestones."
        breadcrumbs={[{ label: 'Notifications' }]}
      />

      {/* HEADER CONTROLS & FILTER TABS */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.5rem' }}>
        <div className="notif-filter-bar">
          <button
            className={`notif-filter-item ${filterTab === 'all' ? 'active' : ''}`}
            onClick={() => setFilterTab('all')}
          >
            All Alerts ({notifications.length})
          </button>
          <button
            className={`notif-filter-item ${filterTab === 'unread' ? 'active' : ''}`}
            onClick={() => setFilterTab('unread')}
          >
            Unread ({unreadCount}) {unreadCount > 0 && <span className="unread-dot-badge" />}
          </button>
          <button
            className={`notif-filter-item ${filterTab === 'task' ? 'active' : ''}`}
            onClick={() => setFilterTab('task')}
          >
            <Code2 size={14} /> Tasks
          </button>
          <button
            className={`notif-filter-item ${filterTab === 'interview' ? 'active' : ''}`}
            onClick={() => setFilterTab('interview')}
          >
            <Video size={14} /> Interviews
          </button>
          <button
            className={`notif-filter-item ${filterTab === 'system' ? 'active' : ''}`}
            onClick={() => setFilterTab('system')}
          >
            <Flame size={14} /> Streaks
          </button>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {unreadCount > 0 && (
            <Button variant="secondary" size="sm" icon={CheckCheck} onClick={handleMarkAllAsRead}>
              Mark All Read
            </Button>
          )}
          <Button variant="ghost" size="sm" icon={Trash2} onClick={handleClearRead}>
            Clear Read
          </Button>
        </div>
      </div>

      {/* NOTIFICATIONS LIST */}
      {filteredNotifs.length === 0 ? (
        <EmptyState title="No Notifications" message="You are all caught up! No notifications match the selected filter." icon={Bell} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: '850px' }}>
          {filteredNotifs.map((notif) => (
            <Card key={notif.id} className={!notif.is_read ? 'notif-card-unread' : ''}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                    <span className={`badge-pill ${notif.type === 'Interview' ? 'badge-amber' : notif.type === 'Task' ? 'badge-primary' : 'badge-emerald'}`}>
                      {notif.type || 'AI Alert'}
                    </span>

                    {!notif.is_read && (
                      <span style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--accent-rose)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                        <span className="unread-dot-badge" /> UNREAD
                      </span>
                    )}

                    <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginLeft: 'auto' }}>
                      {formatDateTime(notif.created_at)}
                    </span>
                  </div>

                  <h4 style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-main)', margin: '0 0 0.25rem 0' }}>
                    {notif.title}
                  </h4>
                  <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', lineHeight: 1.5, margin: 0 }}>
                    {notif.message}
                  </p>

                  {notif.actionUrl && (
                    <div style={{ marginTop: '0.85rem' }}>
                      <Button
                        variant="secondary"
                        size="sm"
                        icon={ArrowRight}
                        onClick={() => navigate(notif.actionUrl)}
                      >
                        {notif.actionLabel || 'View Details'}
                      </Button>
                    </div>
                  )}
                </div>

                {!notif.is_read && (
                  <Button variant="ghost" size="sm" icon={Check} onClick={() => handleMarkAsRead(notif.id)}>
                    Mark Read
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default NotificationPage;

