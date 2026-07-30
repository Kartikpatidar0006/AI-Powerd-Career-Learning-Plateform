import React, { useState, useEffect } from 'react';
import { Bell, Check, Info } from 'lucide-react';
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

  const fetchNotifications = async () => {
    try {
      setLoading(true);
      const data = await notificationService.getMyNotifications();
      setNotifications(Array.isArray(data) ? data : data.items || []);
    } catch (err) {
      setNotifications([]);
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
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
    } catch (err) {
      // Silent error
    }
  };

  if (loading) return <Loader label="Loading notifications..." />;

  return (
    <div>
      <PageHeader
        title="Notifications & Alerts"
        description="Stay updated with task evaluation scores, unlock notifications, and interview reminders."
        breadcrumbs={[{ label: 'Notifications' }]}
      />

      {notifications.length === 0 ? (
        <EmptyState title="No Notifications" message="You have no notifications at this time." icon={Bell} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: '800px' }}>
          {notifications.map((notif) => (
            <Card key={notif.id}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.125rem 0.5rem', borderRadius: 'var(--radius-full)', background: 'var(--primary-light)', color: 'var(--primary)' }}>
                      {notif.type || 'Alert'}
                    </span>
                    {!notif.is_read && (
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--accent-rose)' }}>Unread</span>
                    )}
                  </div>
                  <h4 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)' }}>{notif.title}</h4>
                  <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginTop: '0.25rem', lineHeight: 1.5 }}>
                    {notif.message}
                  </p>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '0.5rem', display: 'block' }}>
                    {formatDateTime(notif.created_at)}
                  </span>
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
