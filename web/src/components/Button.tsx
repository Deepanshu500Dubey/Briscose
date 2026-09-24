import { type ButtonHTMLAttributes, forwardRef } from 'react';

type Variant = 'primary' | 'gold' | 'outline' | 'danger';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

const variantClasses: Record<Variant, string> = {
  primary: 'bg-brand-navy text-white hover:bg-brand-navy-deep',
  gold: 'bg-brand-gold-bright text-ink hover:brightness-95',
  outline: 'bg-transparent text-ink border border-line hover:bg-line-soft',
  danger: 'bg-transparent text-status-bad-fg border border-status-bad-line hover:bg-status-bad-bg',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', className = '', disabled, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg border border-transparent px-4 py-2 font-body text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${variantClasses[variant]} ${className}`}
      {...props}
    />
  );
});
