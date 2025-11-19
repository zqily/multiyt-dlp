import React from 'react';
import { twMerge } from 'tailwind-merge';
import clsx from 'clsx';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link';
  size?: 'default' | 'sm' | 'lg' | 'icon';
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', ...props }, ref) => {
    const variants = {
      default: 'bg-synth-cyan text-synth-navy font-bold hover:shadow-neon-cyan border border-transparent hover:border-white/50',
      destructive: 'bg-synth-pink text-white font-bold hover:shadow-neon-pink border border-transparent',
      outline: 'border-2 border-synth-cyan text-synth-cyan bg-transparent hover:bg-synth-cyan hover:text-synth-navy hover:shadow-neon-cyan',
      secondary: 'bg-synth-dark border border-synth-cyan/30 text-synth-light hover:border-synth-cyan hover:text-synth-cyan',
      ghost: 'hover:bg-synth-cyan/10 hover:text-synth-cyan',
      link: 'text-synth-cyan underline-offset-4 hover:underline',
    };
    const sizes = {
      default: 'h-10 px-4 py-2',
      sm: 'h-9 rounded px-3',
      lg: 'h-12 rounded px-8 text-lg',
      icon: 'h-10 w-10',
    };

    return (
      <button
        className={twMerge(
            clsx(
                'inline-flex items-center justify-center rounded text-sm font-mono transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-synth-pink disabled:pointer-events-none disabled:opacity-50 disabled:grayscale',
                variants[variant],
                sizes[size],
                className
            )
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = 'Button';

export { Button };