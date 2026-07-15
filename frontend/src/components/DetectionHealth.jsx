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
      <div className="glass-panel p-5 flex items-center justify-center min-h-[200px] shadow-sm">
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
    <div className="glass-panel p-5 flex flex-col h-full shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2 drop-shadow-sm">
          <Activity className="w-4 h-4 text-brand-500" />
          Red-Team Detection Health
        </h3>
        <span className={clsx(
          "px-3 py-1 rounded-full text-xs font-bold border shadow-sm",
          isHealthy 
            ? "bg-emerald-100 text-emerald-600 border-emerald-200" 
            : "bg-red-100 text-red-600 border-red-200"
        )}>
          {successRate}% Caught
        </span>
      </div>

      <div className="text-center mb-6 mt-2">
        <div className="text-5xl font-bold text-slate-800 drop-shadow-sm">{report.caught}<span className="text-slate-500 text-2xl font-semibold">/{report.total}</span></div>
        <div className="text-sm text-slate-500 mt-2 font-medium">Evasion variants successfully detected</div>
      </div>

      <div className="space-y-3 flex-1 overflow-y-auto">
        <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Breakdown by Class</h4>
        {Object.entries(report.misses_by_class).map(([className, misses]) => {
          const hasMisses = misses > 0;
          return (
            <div key={className} className="flex items-center justify-between p-3 rounded-xl bg-white/40 border border-white/60 shadow-sm hover:bg-white/60 transition-colors">
              <span className="text-sm font-bold text-slate-700 capitalize">{className.replace('_', ' ')}</span>
              <div className="flex items-center gap-2">
                {hasMisses ? (
                  <span className="text-xs text-red-600 bg-red-100 px-2 py-1 rounded-md border border-red-200 flex items-center gap-1 font-bold shadow-sm">
                    <XCircle className="w-3.5 h-3.5" />
                    {misses} missed
                  </span>
                ) : (
                  <span className="text-xs text-emerald-600 bg-emerald-100 px-2 py-1 rounded-md border border-emerald-200 flex items-center gap-1 font-bold shadow-sm">
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
