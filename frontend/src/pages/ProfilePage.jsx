import React from 'react';
import { User, Mail, Shield, Key } from 'lucide-react';
import useAuth from '../hooks/useAuth';
import PageHeader from '../components/PageHeader/PageHeader';
import Card from '../components/Card/Card';
import Button from '../components/Button/Button';
import Input from '../components/Input/Input';

export const ProfilePage = () => {
  const { user } = useAuth();

  return (
    <div>
      <PageHeader
        title="Account Profile"
        description="Manage your account profile details and authentication credentials."
        breadcrumbs={[{ label: 'Profile' }]}
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', maxWidth: '640px' }}>
        <Card title="User Profile Information">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '0.5rem' }}>
            <Input label="Full Name" type="text" value={user?.full_name || ''} readOnly icon={User} />
            <Input label="Email Address" type="email" value={user?.email || ''} readOnly icon={Mail} />
            <Input label="Role" type="text" value={user?.role?.name || 'Student'} readOnly icon={Shield} />
          </div>
        </Card>

        <Card title="Security & Password">
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
            To update your password, enter your current password and desired new password below.
          </p>
          <form onSubmit={(e) => e.preventDefault()}>
            <Input label="Current Password" type="password" placeholder="••••••••" icon={Key} />
            <Input label="New Password" type="password" placeholder="••••••••" icon={Key} />
            <Button variant="primary" style={{ marginTop: '0.5rem' }}>
              Update Password
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
};

export default ProfilePage;
