import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { StatusBadge } from '../components/StatusBadge';
import { Newspaper, ArrowRightLeft, Building2, MapPin, Loader2 } from 'lucide-react';
import { apiClient } from '../api/client';

export const EntityTimeline = () => {
  // Using a hardcoded ID for now since there's no entity selector yet
  const entityId = 'ent-881';
  
  const { data, isLoading } = useQuery({
    queryKey: ['entity', entityId],
    queryFn: () => apiClient.getEntityTimeline(entityId)
  });

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-brand-400 animate-spin" />
      </div>
    );
  }

  const { entity, timeline } = data || {};

  if (!entity) return null;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <div className="flex justify-between items-start">
          <div>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-brand-500/10 rounded-lg">
                <Building2 className="w-6 h-6 text-brand-400" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-100">{entity.name}</h1>
                <p className="text-sm text-slate-400 font-mono mt-1">{entity.id}</p>
              </div>
            </div>
            
            <div className="flex items-center gap-4 mt-6 text-sm text-slate-300">
              <span className="flex items-center gap-1.5"><MapPin className="w-4 h-4 text-slate-500" /> {entity.country}</span>
              <span className="text-slate-600">|</span>
              <span className="flex items-center gap-1.5"><Building2 className="w-4 h-4 text-slate-500" /> {entity.sector}</span>
            </div>
          </div>
          
          <div className="text-right">
            <div className="text-sm text-slate-400 mb-1">Risk Score</div>
            <div className="text-4xl font-bold text-red-400">{entity.current_score}</div>
          </div>
        </div>

        {/* Flags */}
        <div className="mt-6 pt-6 border-t border-slate-800 flex flex-wrap gap-2">
          {entity.pep_flag && <StatusBadge band="high" className="bg-orange-500/10 text-orange-400" />}
          {entity.fatf_country_flag && <StatusBadge band="critical" className="bg-red-500/10 text-red-400" />}
          {entity.watched && <span className="px-2.5 py-0.5 rounded-full text-xs font-medium border bg-purple-500/10 text-purple-400 border-purple-500/20">Watched</span>}
        </div>
      </div>

      {/* Timeline */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-slate-100 mb-6 flex items-center gap-2">
          <History className="w-5 h-5 text-slate-400" />
          Event Timeline
        </h2>
        
        <div className="relative pl-4 space-y-8 before:absolute before:inset-y-0 before:left-4 before:-ml-px before:w-0.5 before:bg-slate-800">
          {timeline?.map((event) => (
            <div key={event.id} className="relative flex gap-4">
              <div className={`absolute -left-6 w-4 h-4 rounded-full border-2 border-slate-900 flex items-center justify-center ${event.severity === 'high' ? 'bg-red-400' : 'bg-yellow-400'}`}>
              </div>
              
              <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4 flex-1">
                <div className="flex justify-between items-start mb-2">
                  <div className="flex items-center gap-2">
                    {event.type === 'adverse_media' ? (
                      <Newspaper className="w-4 h-4 text-blue-400" />
                    ) : (
                      <ArrowRightLeft className="w-4 h-4 text-emerald-400" />
                    )}
                    <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                      {event.source}
                    </span>
                  </div>
                  <span className="text-xs text-slate-500">
                    {new Date(event.date).toLocaleString()}
                  </span>
                </div>
                
                <h3 className="text-sm font-medium text-slate-200">{event.title}</h3>
                {event.amount && (
                  <p className="text-sm text-slate-400 mt-2 font-mono bg-slate-900/50 inline-block px-2 py-1 rounded">
                    {event.amount}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// Simple History icon fallback
function History(props) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
      <path d="M12 7v5l4 2" />
    </svg>
  );
}
