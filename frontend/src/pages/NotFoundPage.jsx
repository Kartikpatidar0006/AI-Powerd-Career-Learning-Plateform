import React from 'react';
import { useNavigate } from 'react-router-dom';
import { FileQuestion, Home } from 'lucide-react';
import Button from '../components/Button/Button';

export const NotFoundPage = () => {
  const navigate = useNavigate();

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1.5rem', background: 'var(--bg-dark)', textAlign: 'center' }}>
      <div style={{ maxWidth: '440px' }}>
        <div style={{ width: '80px', height: '80px', borderRadius: '50%', background: 'var(--primary-light)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem' }}>
          <FileQuestion size={40} />
        </div>
        <h1 style={{ fontFamily: 'var(--font-heading)', fontSize: '3rem', fontWeight: 800, color: 'var(--text-main)' }}>404</h1>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-main)', margin: '0.5rem 0' }}>Page Not Found</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9375rem', marginBottom: '2rem' }}>
          The page you are looking for does not exist or has been moved.
        </p>
        <Button variant="primary" size="lg" icon={Home} onClick={() => navigate('/dashboard')}>
          Back to Dashboard
        </Button>
      </div>
    </div>
  );
};

export default NotFoundPage;
