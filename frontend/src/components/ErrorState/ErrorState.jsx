import React from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';
import Button from '../Button/Button';

export const ErrorState = ({
  title = 'Something Went Wrong',
  message = 'An unexpected error occurred while loading this page.',
  onRetry,
}) => {
  return (
    <div className="state-container" style={{ borderColor: 'rgba(239, 68, 68, 0.3)' }}>
      <div className="state-icon" style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#ef4444' }}>
        <AlertTriangle size={28} />
      </div>
      <h3 className="state-title">{title}</h3>
      <p className="state-message">{message}</p>
      {onRetry && (
        <Button variant="secondary" icon={RotateCcw} onClick={onRetry}>
          Try Again
        </Button>
      )}
    </div>
  );
};

export default ErrorState;
