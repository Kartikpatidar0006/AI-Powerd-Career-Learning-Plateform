import React from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';

export const Breadcrumb = ({ items = [] }) => {
  if (!items.length) return null;

  return (
    <nav className="breadcrumb-nav">
      <Link to="/dashboard" className="breadcrumb-link">
        Home
      </Link>
      {items.map((item, index) => (
        <React.Fragment key={index}>
          <ChevronRight size={14} />
          {item.path ? (
            <Link to={item.path} className="breadcrumb-link">
              {item.label}
            </Link>
          ) : (
            <span style={{ color: 'var(--text-main)', fontWeight: 500 }}>{item.label}</span>
          )}
        </React.Fragment>
      ))}
    </nav>
  );
};

export default Breadcrumb;
