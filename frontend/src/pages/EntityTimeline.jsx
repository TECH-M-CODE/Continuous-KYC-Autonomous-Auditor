import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { StatusBadge } from '../components/StatusBadge';
import { EntitySelector } from '../components/EntitySelector';
import { RiskGauge } from '../components/RiskGauge';
import {
  Newspaper, ArrowRightLeft, Building2, User, MapPin,
  Loader2, Briefcase, Users, Globe, AlertTriangle
} from 'lucide-react';
import { apiClient } from '../api/client';
import clsx from 'clsx';

const EVENT_ICON = {
  ADVERSE_MEDIA:    { icon: Newspaper,       color: 'text-blue-400',    bg: 'bg-blue-500/10' },
  TRANSACTION:      { icon: ArrowRightLeft,   color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  SANCTIONS_HIT:    { icon: AlertTriangle,    color: 'text-red-400',     bg: 'bg-red-500/10' },
  default:          { icon: AlertTriangle,    color: 'text-slate-400',   bg: 'bg-slate-700/50' },
};

function getEventMeta(category = '') {
  return EVENT_ICON[category] || EVENT_ICON.default;
}

export const EntityTimeline = () => {
  const { entityId } = useParams();
  const navigate = useNavigate();

  const { data: entity, isLoading } = useQuery({
    queryKey: ['entity', entityId],
    queryFn: () => apiClient.getEntityTimeline(entityId),
    enabled: !!entityId,
  });

  const { data: entityAlerts = [] } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => apiClient.getAlerts({ limit: 100 }),
    enabled: !!entityId,
  });

  const relatedAlerts = entityAlerts.filter(a => a.entity_id === entityId).slice(0, 5);

  return (
    <div className="flex h-full gap-5 max-w-7xl mx-auto w-full">

      {/* ── Left: Entity Selector ── */}
      <div className="w-56 shrink-0 glass-card rounded-2xl p-3 flex flex-col overflow-hidden">
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 px-1">
          Entities
        </h2>
        <EntitySelector basePath="/timeline" selectedId={entityId} />
      </div>

      {/* ── Right: Entity Detail ── */}
      <div className="flex-1 overflow-y-auto space-y-4">
        {!entityId && (
          <div className="flex h-64 items-center justify-center text-slate-600 text-sm">
            ← Select an entity from the list
          </div>
        )}

        {entityId && isLoading && (
          <div className="flex h-64 items-center justify-center">
            <Loader2 className="w-7 h-7 text-brand-400 animate-spin" />
          </div>
        )}

        {entity && (
          <>
            {/* Header Card */}
            <div className="glass-card rounded-2xl p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-4">
                  <div className="p-3 rounded-xl bg-brand-500/10 border border-brand-500/20 shrink-0">
                    {entity.type === 'Person'
                      ? <User className="w-6 h-6 text-brand-400" />
                      : <Building2 className="w-6 h-6 text-brand-400" />}
                  </div>
                  <div>
                    <h1 className="text-xl font-bold text-white">{entity.name}</h1>
                    <p className="text-xs font-mono text-slate-500 mt-0.5">{entity.id}</p>
                    <div className="flex items-center gap-4 mt-3 text-xs text-slate-400">
                      {entity.jurisdiction && (
                        <span className="flex items-center gap-1.5">
                          <MapPin className="w-3.5 h-3.5 text-slate-600" /> {entity.jurisdiction}
                        </span>
                      )}
                      {entity.type && (
                        <span className="flex items-center gap-1.5">
                          <Briefcase className="w-3.5 h-3.5 text-slate-600" /> {entity.type}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Risk Gauge */}
                <div className="shrink-0">
                  <RiskGauge score={entity.risk_score || 0} size={110} label="Risk Score" />
                </div>
              </div>

              {/* PEPs */}
              {entity.peps?.length > 0 && (
                <div className="mt-4 pt-4 border-t border-slate-800 flex flex-wrap gap-2">
                  {entity.peps.map(pep => (
                    <span key={pep.id} className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border bg-orange-500/10 text-orange-400 border-orange-500/20">
                      <Users className="w-3 h-3" /> PEP: {pep.full_name} ({pep.role})
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* KYC Profile Summary */}
            {(entity.industry || entity.beneficial_owners || entity.executives) && (
              <div className="glass-card rounded-2xl p-5">
                <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                  <Globe className="w-4 h-4 text-brand-400" />
                  KYC Profile
                </h2>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-xs">
                  {entity.industry && (
                    <div>
                      <p className="text-slate-500 mb-1">Industry</p>
                      <p className="text-slate-200 font-medium">{entity.industry}</p>
                    </div>
                  )}
                  {entity.registration_country && (
                    <div>
                      <p className="text-slate-500 mb-1">Registered In</p>
                      <p className="text-slate-200 font-medium">{entity.registration_country}</p>
                    </div>
                  )}
                  {entity.executives && (
                    <div>
                      <p className="text-slate-500 mb-1">Executives</p>
                      <p className="text-slate-200 font-medium">{entity.executives}</p>
                    </div>
                  )}
                  {entity.beneficial_owners && (
                    <div>
                      <p className="text-slate-500 mb-1">Beneficial Owners</p>
                      <p className="text-slate-200 font-medium">{entity.beneficial_owners}</p>
                    </div>
                  )}
                  {entity.kyc_status && (
                    <div>
                      <p className="text-slate-500 mb-1">KYC Status</p>
                      <p className={clsx('font-semibold', entity.kyc_status === 'Approved' ? 'text-emerald-400' : 'text-amber-400')}>
                        {entity.kyc_status}
                      </p>
                    </div>
                  )}
                  {entity.monitoring_status && (
                    <div>
                      <p className="text-slate-500 mb-1">Monitoring</p>
                      <p className="text-slate-200 font-medium">{entity.monitoring_status}</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Related Alerts */}
            {relatedAlerts.length > 0 && (
              <div className="glass-card rounded-2xl p-5">
                <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-400" />
                  Related Alerts ({relatedAlerts.length})
                </h2>
                <div className="space-y-2">
                  {relatedAlerts.map(a => (
                    <div key={a.id} className="flex items-center gap-3 p-2.5 rounded-xl bg-slate-800/40 border border-slate-700/50">
                      <StatusBadge band={a.priority?.toLowerCase()} />
                      <p className="text-xs text-slate-300 flex-1 truncate">{a.summary || a.id}</p>
                      <span className={clsx(
                        'text-[10px] font-medium px-1.5 py-0.5 rounded-full border',
                        a.status === 'OPEN' ? 'text-amber-400 bg-amber-500/10 border-amber-500/20' : 'text-slate-500 bg-slate-800 border-slate-700'
                      )}>{a.status}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Event Timeline */}
            <div className="glass-card rounded-2xl p-5">
              <h2 className="text-sm font-semibold text-slate-300 mb-5 flex items-center gap-2">
                <ArrowRightLeft className="w-4 h-4 text-slate-400" />
                Event Timeline
              </h2>

              <div className="relative space-y-0">
                {entity.recent_events?.map((event, idx) => {
                  const meta = getEventMeta(event.event_category);
                  const Icon = meta.icon;
                  const isLast = idx === (entity.recent_events.length - 1);
                  return (
                    <div key={event.id || idx} className="relative flex gap-4">
                      {/* Connector */}
                      {!isLast && (
                        <div className="absolute left-[19px] top-10 bottom-0 w-px bg-slate-800" />
                      )}
                      {/* Icon */}
                      <div className={clsx('relative z-10 w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border border-slate-700/50', meta.bg)}>
                        <Icon className={clsx('w-4 h-4', meta.color)} />
                      </div>
                      {/* Content */}
                      <div className="flex-1 pb-5">
                        <div className="glass-card rounded-xl p-3.5">
                          <div className="flex items-start justify-between gap-2 mb-1">
                            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                              {event.event_category?.replace(/_/g, ' ')}
                            </span>
                            <span className="text-xs text-slate-600 shrink-0">
                              {new Date(event.created_at).toLocaleString()}
                            </span>
                          </div>
                          <p className="text-sm text-slate-200">{event.reasoning}</p>
                          {event.score_delta != null && (
                            <span className="inline-flex items-center gap-1 mt-2 text-xs font-mono bg-slate-900 px-2 py-0.5 rounded text-orange-400">
                              Score Δ +{event.score_delta}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
                {(!entity.recent_events || entity.recent_events.length === 0) && (
                  <div className="text-center text-slate-600 text-sm py-10">
                    No recent events for this entity.
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
