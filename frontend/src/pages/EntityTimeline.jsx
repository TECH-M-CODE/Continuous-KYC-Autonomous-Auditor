import React, { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { StatusBadge } from '../components/StatusBadge';
import { Newspaper, ArrowRightLeft, Building2, MapPin, Loader2 } from 'lucide-react';
import { apiClient } from '../api/client';

export const EntityTimeline = () => {
  const { entityId } = useParams();
  const navigate = useNavigate();

  // No entity in the URL yet (e.g. landed on the bare /timeline nav link) —
  // fall back to the first entity in the watchlist and redirect into its URL.
  const { data: entities = [] } = useQuery({
    queryKey: ['watchlist'],
    queryFn: apiClient.getWatchlist,
    enabled: !entityId,
  });

  useEffect(() => {
    if (!entityId && entities.length > 0) {
      navigate(`/timeline/${entities[0].id}`, { replace: true });
    }
  }, [entityId, entities, navigate]);

  const { data: entity, isLoading } = useQuery({
    queryKey: ['entity', entityId],
    queryFn: () => apiClient.getEntityTimeline(entityId),
    enabled: !!entityId,
  });

  if (isLoading || !entityId) {
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
      <div className="glass-panel p-6 shadow-sm">
        <div className="flex justify-between items-start">
          <div>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-white/60 rounded-xl shadow-sm border border-white/80">
                <Building2 className="w-6 h-6 text-brand-600" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-800 drop-shadow-sm">{entity.name}</h1>
                <p className="text-sm text-slate-500 font-mono font-medium mt-1">{entity.id}</p>
              </div>
            </div>
            
            <div className="flex items-center gap-4 mt-6 text-sm text-slate-600 font-semibold">
              <span className="flex items-center gap-1.5"><MapPin className="w-4 h-4 text-brand-500" /> {entity.jurisdiction}</span>
              <span className="text-slate-400">|</span>
              <span className="flex items-center gap-1.5"><Building2 className="w-4 h-4 text-brand-500" /> {entity.type}</span>
            </div>
          </div>
          
          <div className="text-right">
            <div className="text-sm font-bold text-slate-500 mb-1 uppercase tracking-wider">Risk Score</div>
            <div className="text-4xl font-bold text-red-500 drop-shadow-sm mb-2">{entity.risk_score}</div>
            <StatusBadge band={entity.risk_band?.toLowerCase()} />
          </div>
        </div>

        {/* PEPs */}
        {entity.peps?.length > 0 && (
          <div className="mt-6 pt-6 border-t border-white/50 flex flex-wrap gap-2">
            {entity.peps.map(pep => (
              <span key={pep.id} className="px-3 py-1 rounded-full text-xs font-bold border shadow-sm bg-orange-100 text-orange-600 border-orange-200">
                PEP: {pep.full_name} ({pep.role})
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Timeline from recent_events */}
      <div className="glass-panel p-6 shadow-sm">
        <h2 className="text-lg font-bold text-slate-800 mb-6 flex items-center gap-2 drop-shadow-sm">
          <History className="w-5 h-5 text-brand-500" />
          Event Timeline
        </h2>
        
        <div className="relative pl-4 space-y-8 before:absolute before:inset-y-0 before:left-4 before:-ml-px before:w-0.5 before:bg-white/60">
          {entity.recent_events?.map((event) => (
            <div key={event.id} className="relative flex gap-4">
              <div className={`absolute -left-6 w-4 h-4 rounded-full border-2 border-white flex items-center justify-center shadow-sm ${event.severity === 'CRITICAL' || event.severity === 'HIGH' ? 'bg-red-500' : 'bg-amber-400'}`}>
              </div>
              
              <div className="bg-white/40 border border-white/60 rounded-xl p-5 flex-1 shadow-sm hover:bg-white/60 transition-colors">
                <div className="flex justify-between items-start mb-3">
                  <div className="flex items-center gap-2">
                    {event.event_category === 'ADVERSE_MEDIA' ? (
                      <Newspaper className="w-4 h-4 text-brand-500" />
                    ) : (
                      <ArrowRightLeft className="w-4 h-4 text-emerald-500" />
                    )}
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                      {event.event_category?.replace('_', ' ')}
                    </span>
                  </div>
                  <span className="text-xs font-semibold text-slate-500">
                    {new Date(event.created_at).toLocaleString()}
                  </span>
                </div>
                
                <h3 className="text-sm font-bold text-slate-800 leading-relaxed">{event.reasoning}</h3>
                {event.score_delta != null && (
                  <p className="text-sm text-red-600 mt-3 font-mono font-bold bg-red-100 inline-block px-3 py-1.5 rounded-lg border border-red-200 shadow-sm">
                    Score Δ: +{event.score_delta}
                  </p>
                )}
              </div>
            </div>
          ))}

          {(!entity.recent_events || entity.recent_events.length === 0) && (
            <div className="text-center text-slate-500 font-semibold py-8">No recent events for this entity.</div>
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
