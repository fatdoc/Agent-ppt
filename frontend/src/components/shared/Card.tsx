import React from 'react';
import { cn } from '@/utils';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  hoverable?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  hoverable = false,
  className,
  ...props
}) => {
  return (
    <div
      className={cn(
        'bg-white/90 dark:bg-background-secondary rounded-lg shadow-[0_18px_45px_rgba(18,18,18,0.06)] border border-[#121212]/10 dark:border-border-primary',
        hoverable && 'hover:shadow-[0_22px_60px_rgba(18,18,18,0.1)] hover:-translate-y-1 hover:border-banana-500 transition-all duration-200 cursor-pointer',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};
