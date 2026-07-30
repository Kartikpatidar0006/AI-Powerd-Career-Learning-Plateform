import React from 'react';
import { Inbox } from 'lucide-react';
import Button from '../Button/Button';

export const EmptyState = ({
  title = 'No Data Found',
  message = 'There are no items to display at the moment.',
  icon: Icon = Inbox,
  actionLabel,
  onAction,
}) => {
  return (
    <div className="state-container">
      <div className="state-icon">
        <Icon size={28} />
      </div>
      <h3 className="state-title">{title}</h3>
      <p className="state-message">{message}</p>
      {actionLabel && onAction && (
        <Button variant="primary" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
};

export default EmptyState;
