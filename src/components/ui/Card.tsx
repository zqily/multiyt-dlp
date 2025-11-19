import React from "react";
import { twMerge } from "tailwind-merge";

const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={twMerge(
      "rounded-xl border-2 border-synth-cyan/20 bg-synth-dark/90 backdrop-blur-sm shadow-lg text-synth-light relative overflow-hidden group transition-all hover:border-synth-cyan/50", 
      className
    )}
    {...props}
  >
    {/* Decorative corner accent */}
    <div className="absolute top-0 right-0 w-4 h-4 border-t-2 border-r-2 border-synth-pink opacity-50 group-hover:opacity-100 transition-opacity" />
    <div className="absolute bottom-0 left-0 w-4 h-4 border-b-2 border-l-2 border-synth-pink opacity-50 group-hover:opacity-100 transition-opacity" />
    {props.children}
  </div>
));
Card.displayName = "Card";

const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={twMerge("flex flex-col space-y-1.5 p-6", className)}
    {...props}
  />
));
CardHeader.displayName = "CardHeader";

const CardTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={twMerge("text-xl font-bold leading-none tracking-wider text-synth-cyan uppercase font-mono", className)}
    {...props}
  />
));
CardTitle.displayName = "CardTitle";


const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={twMerge("p-6 pt-0", className)} {...props} />
));
CardContent.displayName = "CardContent";

export { Card, CardHeader, CardTitle, CardContent };