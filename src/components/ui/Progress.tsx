import React from 'react';
import { twMerge } from 'tailwind-merge';

interface ProgressProps extends React.ProgressHTMLAttributes<HTMLProgressElement> {}

const Progress = React.forwardRef<HTMLProgressElement, ProgressProps>(
  ({ className, value, ...props }, ref) => {
    return (
      <progress
        ref={ref}
        value={value}
        className={twMerge(
          'relative h-2 w-full overflow-hidden rounded-full bg-zinc-700',
          '[&::-webkit-progress-bar]:rounded-full [&::-webkit-progress-bar]:bg-zinc-700',
          '[&::-webkit-progress-value]:rounded-full [&::-webkit-progress-value]:bg-blue-600 [&::-webkit-progress-value]:transition-all',
          '[&::-moz-progress-bar]:rounded-full [&::-moz-progress-bar]:bg-blue-600 [&::-moz-progress-bar]:transition-all',
          className
        )}
        {...props}
      />
    );
  }
);

Progress.displayName = 'Progress';

export { Progress };
