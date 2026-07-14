import React, { useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import { DecisionGraph } from '../components/DecisionGraph';
import { ArrowLeft, Loader2, AlertCircle } from 'lucide-react';

export default function TraceView() {
  const { id } = useParams();

  const { data: trace, isLoading, error } = useQuery({
    queryKey: ['trace', id],
    queryFn: () => apiClient.getTrace(id)
  });

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center bg-slate-950">
        <Loader2 className="w-8 h-8 text-brand-400 animate-spin" />
      </div>
    );
  }

  if (error || !trace) {
    return (
      <div className="p-8 text-center bg-slate-950 h-full flex flex-col items-center justify-center">
        <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
        <h2 className="text-xl font-bold text-slate-200 mb-2">Failed to load trace</h2>
        <p className="text-slate-400">Could not retrieve decision trace for event {id}</p>
        <Link to="/" className="mt-6 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg">
          Return Home
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-slate-950">
      <div className="h-16 border-b border-slate-800 flex items-center px-6 shrink-0 bg-slate-900">
        <Link to="/" className="flex items-center gap-2 text-slate-400 hover:text-slate-200 transition-colors mr-6">
          <ArrowLeft className="w-5 h-5" />
          <span className="text-sm font-medium">Back to Alerts</span>
        </Link>
        <div className="h-6 w-px bg-slate-800 mr-6"></div>
        <div>
          <h1 className="text-lg font-bold text-slate-200 leading-tight">Decision Trace</h1>
          <div className="text-xs text-slate-500">Event: {trace.event_id} • Target: {trace.entity_id}</div>
        </div>
        <div className="ml-auto">
          <span className={`px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider
            ${trace.final_outcome.includes('alert') ? 'bg-red-500/20 text-red-400 border border-red-900/50' : 
              trace.final_outcome === 'dismissed' ? 'bg-slate-800 text-slate-400 border border-slate-700' :
              'bg-blue-500/20 text-blue-400 border border-blue-900/50'}`}
          >
            Outcome: {trace.final_outcome.replace('_', ' ')}
          </span>
        </div>
      </div>
      
      <div className="flex-1 relative">
        <DecisionGraph trace={trace} />
      </div>
    </div>
  );
}
