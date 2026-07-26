import React, { useId } from 'react';
import { cn } from './cn';

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => <input ref={ref} className={cn('app-input', className)} {...props} />,
);
Input.displayName = 'Input';

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, ...props }, ref) => <select ref={ref} className={cn('ds-select', className)} {...props} />,
);
Select.displayName = 'Select';

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => <textarea ref={ref} className={cn('ds-textarea', className)} {...props} />,
);
Textarea.displayName = 'Textarea';

interface FormFieldProps {
  label: React.ReactNode;
  children: React.ReactElement<{ id?: string; 'aria-describedby'?: string; 'aria-invalid'?: boolean }>;
  id?: string;
  helpText?: React.ReactNode;
  error?: React.ReactNode;
  className?: string;
  required?: boolean;
}

export const FormField: React.FC<FormFieldProps> = ({
  label, children, id, helpText, error, className, required = false,
}) => {
  const generatedId = useId();
  const controlId = id ?? generatedId;
  const descriptionId = helpText || error ? `${controlId}-description` : undefined;

  return (
    <div className={cn('ds-form-field', className)}>
      <label className="ds-label" htmlFor={controlId}>
        {label}{required ? <span aria-hidden="true"> *</span> : null}
      </label>
      {React.cloneElement(children, {
        id: controlId,
        'aria-describedby': descriptionId,
        'aria-invalid': Boolean(error),
      })}
      {helpText || error ? (
        <div id={descriptionId} className={error ? 'ds-error-text' : 'ds-help-text'}>
          {error ?? helpText}
        </div>
      ) : null}
    </div>
  );
};
