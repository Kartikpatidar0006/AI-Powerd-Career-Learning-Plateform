import React, { forwardRef } from 'react';

export const Textarea = forwardRef(({
  label,
  error,
  rows = 4,
  placeholder = '',
  className = '',
  id,
  ...props
}, ref) => {
  const textareaId = id || props.name;

  return (
    <div className="form-group">
      {label && <label htmlFor={textareaId} className="form-label">{label}</label>}
      <textarea
        ref={ref}
        id={textareaId}
        rows={rows}
        placeholder={placeholder}
        className={`textarea-field ${error ? 'is-error' : ''} ${className}`}
        {...props}
      />
      {error && <span className="form-error">{error}</span>}
    </div>
  );
});

Textarea.displayName = 'Textarea';

export default Textarea;
