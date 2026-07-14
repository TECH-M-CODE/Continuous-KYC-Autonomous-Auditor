import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { ShieldAlert, Activity, Loader2, CheckCircle, XCircle } from 'lucide-react';
import { apiClient } from '../api/client';
import clsx from 'clsx';

export const DetectionHealth = () => {
  const { data: report, isLoading } = useQuery({
    queryKey: ['drillReport'],
    queryFn: apiClient.getDrillReport,
    refetchInterval: 30000 // Refetch every 30s to keep it fresh
  });

  if (isLoading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex items-center justify-center min-h-[200px]">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
      </div>
    );
  }

  if (!report) {
    return null;
  }

  const successRate = Math.round((report.caught / report.total) * 100);
  const isHealthy = successRate >= 80;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col h-full">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
          <Activity className="w-4 h-4 text-brand-400" />
          Red-Team Detection Health
        </h3>
        <span className={clsx(
          "px-2 py-0.5 rounded text-xs font-medium border",
          isHealthy 
            ? "bg-green-500/10 text-green-400 border-green-500/20" 
            : "bg-red-500/10 text-red-400 border-red-500/20"
        )}>
          {successRate}% Caught
        </span>
      </div>

      <div className="text-center mb-6 mt-2">
        <div className="text-4xl font-bold text-slate-100">{report.caught}<span className="text-slate-500 text-2xl font-normal">/{report.total}</span></div>
        <div className="text-sm text-slate-400 mt-1">Evasion variants successfully detected</div>
      </div>

      <div className="space-y-3 flex-1 overflow-y-auto">
        <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Breakdown by Class</h4>
        {Object.entries(report.misses_by_class).map(([className, misses]) => {
          const hasMisses = misses > 0;
          return (
            <div key={className} className="flex items-center justify-between p-2 rounded-lg bg-slate-800/50 border border-slate-700/50">
              <span className="text-sm text-slate-300 capitalize">{className.replace('_', ' ')}</span>
              <div className="flex items-center gap-2">
                {hasMisses ? (
                  <span className="text-xs text-red-400 flex items-center gap-1 font-medium">
                    <XCircle className="w-3.5 h-3.5" />
                    {misses} missed
                  </span>
                ) : (
                  <span className="text-xs text-emerald-400 flex items-center gap-1 font-medium">
                    <CheckCircle className="w-3.5 h-3.5" />
                    Perfect
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
