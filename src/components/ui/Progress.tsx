import React from 'react';
import { twMerge } from 'tailwind-merge';

interface ProgressProps extends React.ProgressHTMLAttributes<HTMLProgressElement> {
    variant?: 'cyan' | 'pink' | 'green' | 'red';
}

const Progress = React.forwardRef<HTMLProgressElement, ProgressProps>(
  ({ className, value, variant = 'cyan' }) => {
    
    const variants = {
        cyan: {
            bar: 'from-synth-cyan to-blue-500 shadow-[0_0_10px_rgba(8,217,214,0.5)]',
            bg: 'bg-synth-dark',
        },
        pink: {
            bar: 'from-synth-pink to-purple-600 shadow-[0_0_10px_rgba(255,46,99,0.5)]',
            bg: 'bg-synth-dark',
        },
        green: {
            bar: 'from-green-400 to-emerald-600 shadow-[0_0_10px_rgba(74,222,128,0.5)]',
            bg: 'bg-green-900/20',
        },
        red: {
            bar: 'from-red-500 to-orange-600 shadow-[0_0_10px_rgba(239,68,68,0.5)]',
            bg: 'bg-red-900/20',
        }
    };

    const currentVariant = variants[variant];

    return (
      <div className={twMerge("relative w-full h-3 rounded-full border border-synth-navy shadow-inner overflow-hidden", currentVariant.bg, className)}>
        <div 
            className={twMerge(
                "h-full bg-gradient-to-r transition-all duration-300 ease-out relative",
                currentVariant.bar
            )}
            style={{ width: `${value}%` }}
        >
            {/* Shimmer effect on the bar */}
            <div className="absolute inset-0 bg-white/20 w-full h-full animate-pulse"></div>
        </div>
      </div>
    );
  }
);

Progress.displayName = 'Progress';

export { Progress };