import React from 'react';
import { twMerge } from 'tailwind-merge';
import clsx from 'clsx';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link' | 'neon';
  size?: 'default' | 'sm' | 'lg' | 'icon';
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', ...props }, ref) => {
    const variants = {
      // Primary Action - The "Cyan Arrow" feel
      default: 'bg-theme-cyan text-black font-bold hover:bg-theme-cyan/90 hover:shadow-glow-cyan border border-transparent',
      
      // Destructive - The "Red Text" feel
      destructive: 'bg-theme-red/10 text-theme-red hover:bg-theme-red/20 border border-theme-red/20 hover:border-theme-red/50',
      
      // Standard UI
      outline: 'border border-zinc-800 bg-transparent hover:bg-zinc-900 text-zinc-300 hover:text-white hover:border-zinc-700',
      secondary: 'bg-zinc-900 text-zinc-100 hover:bg-zinc-800 border border-zinc-800',
      ghost: 'hover:bg-zinc-900 hover:text-theme-cyan text-zinc-400',
      link: 'text-theme-cyan underline-offset-4 hover:underline',
      
      // Special High Visibility
      neon: 'bg-transparent border border-theme-cyan text-theme-cyan hover:bg-theme-cyan hover:text-black shadow-glow-cyan',
    };
    
    const sizes = {
      default: 'h-10 px-4 py-2',
      sm: 'h-8 rounded-md px-3 text-xs',
      lg: 'h-11 rounded-md px-8',
      icon: 'h-9 w-9',
    };

    return (
      <button
        className={twMerge(
            clsx(
                'inline-flex items-center justify-center rounded-md text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-theme-cyan disabled:pointer-events-none disabled:opacity-50 disabled:grayscale',
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