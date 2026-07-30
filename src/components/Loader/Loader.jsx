import React from 'react';

export const Loader = ({ fullScreen = false, size = 'md', label = 'Loading...' }) => {
  const dimensions = size === 'sm' ? '24px' : size === 'lg' ? '48px' : '36px';

  if (fullScreen) {
    return (
      <div style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'var(--bg-dark)',
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '1rem',
      }}>
        <div className="loader-spinner" style={{ width: dimensions, height: dimensions }}></div>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9375rem' }}>{label}</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '2rem', gap: '0.75rem' }}>
      <div className="loader-spinner" style={{ width: dimensions, height: dimensions }}></div>
      {label && <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>{label}</p>}
    </div>
  );
};

export default Loader;
