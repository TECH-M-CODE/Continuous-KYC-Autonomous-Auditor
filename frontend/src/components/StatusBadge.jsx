import React from 'react';
import clsx from 'clsx';
import { twMerge } from 'tailwind-merge';

export const StatusBadge = ({ band, className }) => {
  const baseClasses = "px-2.5 py-0.5 rounded-full text-xs font-medium capitalize border";
  
  let colorClasses = "";
  switch (band?.toLowerCase()) {
    case 'critical':
      colorClasses = "bg-red-500/10 text-red-400 border-red-500/20";
      break;
    case 'high':
      colorClasses = "bg-orange-500/10 text-orange-400 border-orange-500/20";
      break;
    case 'medium':
      colorClasses = "bg-yellow-500/10 text-yellow-400 border-yellow-500/20";
      break;
    case 'low':
      colorClasses = "bg-green-500/10 text-green-400 border-green-500/20";
      break;
    default:
      colorClasses = "bg-slate-500/10 text-slate-400 border-slate-500/20";
  }

  return (
    <span className={twMerge(clsx(baseClasses, colorClasses), className)}>
      {band || 'Unknown'}
    </span>
  );
};
