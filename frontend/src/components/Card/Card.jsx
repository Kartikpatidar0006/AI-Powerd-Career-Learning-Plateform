import React from 'react';

export const Card = ({
  children,
  title,
  subtitle,
  headerAction,
  footer,
  interactive = false,
  className = '',
  onClick,
}) => {
  return (
    <div
      onClick={onClick}
      className={`card ${interactive ? 'card-interactive' : ''} ${className}`}
    >
      {(title || subtitle || headerAction) && (
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            {title && <h3 className="card-title">{title}</h3>}
            {subtitle && <p className="card-subtitle">{subtitle}</p>}
          </div>
          {headerAction && <div>{headerAction}</div>}
        </div>
      )}
      <div className="card-body">{children}</div>
      {footer && <div className="card-footer" style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid var(--border-subtle)' }}>{footer}</div>}
    </div>
  );
};

export default Card;
