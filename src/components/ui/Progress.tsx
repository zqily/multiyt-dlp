import React from 'react';
import { twMerge } from 'tailwind-merge';

interface ProgressProps extends React.ProgressHTMLAttributes<HTMLProgressElement> {
    variant?: 'default' | 'success' | 'error';
}

const Progress = React.forwardRef<HTMLProgressElement, ProgressProps>(
  ({ className, value, variant = 'default' }) => {
    
    // Default maps to our Cyan theme
    const colors = {
        default: 'bg-theme-cyan shadow-[0_0_10px_rgba(0,242,234,0.4)]',
        success: 'bg-emerald-500',
        error: 'bg-theme-red shadow-[0_0_10px_rgba(255,0,80,0.4)]',
    };

    return (
      <div className={twMerge("relative w-full h-1 bg-zinc-900 rounded-full overflow-hidden", className)}>
        <div 
            className={twMerge(
                "h-full transition-all duration-300 ease-out rounded-full",
                colors[variant] || colors.default
            )}
            style={{ width: `${value}%` }}
        />
      </div>
    );
  }
);

Progress.displayName = 'Progress';

export { Progress };