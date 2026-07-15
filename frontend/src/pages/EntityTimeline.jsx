import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { StatusBadge } from '../components/StatusBadge';
import { Newspaper, ArrowRightLeft, Building2, MapPin, Loader2 } from 'lucide-react';
import { apiClient } from '../api/client';

export const EntityTimeline = () => {
  // Using a hardcoded ID matching the backend mock data
  const entityId = 'entity-1';
  
  const { data: entity, isLoading } = useQuery({
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
              <span className="flex items-center gap-1.5"><MapPin className="w-4 h-4 text-slate-500" /> {entity.jurisdiction}</span>
              <span className="text-slate-600">|</span>
              <span className="flex items-center gap-1.5"><Building2 className="w-4 h-4 text-slate-500" /> {entity.type}</span>
            </div>
          </div>
          
          <div className="text-right">
            <div className="text-sm text-slate-400 mb-1">Risk Score</div>
            <div className="text-4xl font-bold text-red-400">{entity.risk_score}</div>
            <StatusBadge band={entity.risk_band?.toLowerCase()} />
          </div>
        </div>

        {/* PEPs */}
        {entity.peps?.length > 0 && (
          <div className="mt-6 pt-6 border-t border-slate-800 flex flex-wrap gap-2">
            {entity.peps.map(pep => (
              <span key={pep.id} className="px-2.5 py-0.5 rounded-full text-xs font-medium border bg-orange-500/10 text-orange-400 border-orange-500/20">
                PEP: {pep.full_name} ({pep.role})
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Timeline from recent_events */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-slate-100 mb-6 flex items-center gap-2">
          <History className="w-5 h-5 text-slate-400" />
          Event Timeline
        </h2>
        
        <div className="relative pl-4 space-y-8 before:absolute before:inset-y-0 before:left-4 before:-ml-px before:w-0.5 before:bg-slate-800">
          {entity.recent_events?.map((event) => (
            <div key={event.id} className="relative flex gap-4">
              <div className={`absolute -left-6 w-4 h-4 rounded-full border-2 border-slate-900 flex items-center justify-center ${event.severity === 'CRITICAL' || event.severity === 'HIGH' ? 'bg-red-400' : 'bg-yellow-400'}`}>
              </div>
              
              <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4 flex-1">
                <div className="flex justify-between items-start mb-2">
                  <div className="flex items-center gap-2">
                    {event.event_category === 'ADVERSE_MEDIA' ? (
                      <Newspaper className="w-4 h-4 text-blue-400" />
                    ) : (
                      <ArrowRightLeft className="w-4 h-4 text-emerald-400" />
                    )}
                    <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                      {event.event_category?.replace('_', ' ')}
                    </span>
                  </div>
                  <span className="text-xs text-slate-500">
                    {new Date(event.created_at).toLocaleString()}
                  </span>
                </div>
                
                <h3 className="text-sm font-medium text-slate-200">{event.reasoning}</h3>
                {event.score_delta != null && (
                  <p className="text-sm text-slate-400 mt-2 font-mono bg-slate-900/50 inline-block px-2 py-1 rounded">
                    Score Δ: +{event.score_delta}
                  </p>
                )}
              </div>
            </div>
          ))}

          {(!entity.recent_events || entity.recent_events.length === 0) && (
            <div className="text-center text-slate-500 py-8">No recent events for this entity.</div>
          )}
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
