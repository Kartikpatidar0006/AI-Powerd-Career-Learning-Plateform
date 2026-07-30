import React, { forwardRef } from 'react';

export const Input = forwardRef(({
  label,
  error,
  type = 'text',
  placeholder = '',
  icon: Icon = null,
  className = '',
  id,
  ...props
}, ref) => {
  const inputId = id || props.name;

  return (
    <div className="form-group">
      {label && <label htmlFor={inputId} className="form-label">{label}</label>}
      <div className="input-wrapper">
        {Icon && <span className="input-icon-left"><Icon size={18} /></span>}
        <input
          ref={ref}
          id={inputId}
          type={type}
          placeholder={placeholder}
          className={`input-field ${Icon ? 'has-icon-left' : ''} ${error ? 'is-error' : ''} ${className}`}
          {...props}
        />
      </div>
      {error && <span className="form-error">{error}</span>}
    </div>
  );
});

Input.displayName = 'Input';

export default Input;
