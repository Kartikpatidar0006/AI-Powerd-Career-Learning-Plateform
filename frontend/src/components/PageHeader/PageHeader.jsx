import React from 'react';
import Breadcrumb from '../Breadcrumb/Breadcrumb';

export const PageHeader = ({ title, description, breadcrumbs, action }) => {
  return (
    <div className="page-header">
      {breadcrumbs && <Breadcrumb items={breadcrumbs} />}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 className="page-title">{title}</h1>
          {description && <p className="page-description">{description}</p>}
        </div>
        {action && <div>{action}</div>}
      </div>
    </div>
  );
};

export default PageHeader;
