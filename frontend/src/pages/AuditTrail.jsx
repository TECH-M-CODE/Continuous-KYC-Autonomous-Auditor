import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { History, Loader2, ShieldCheck, ShieldX } from 'lucide-react';
import { apiClient } from '../api/client';
import { ChainVerifyBadge } from '../components/ChainVerifyBadge';

export const AuditTrail = () => {
  const { entityId } = useParams();
  const navigate = useNavigate();

  // When no entity is in the URL, fetch the watchlist and redirect to the first entity.
  const { data: entities = [] } = useQuery({
    queryKey: ['watchlist'],
    queryFn: apiClient.getWatchlist,
    enabled: !entityId,
  });

  React.useEffect(() => {
    if (!entityId && entities.length > 0) {
      navigate(`/audit/${entities[0].id}`, { replace: true });
    }
  }, [entityId, entities, navigate]);

  // Also fetch the full watchlist for the entity selector dropdown (always enabled).
  const { data: allEntities = [] } = useQuery({
    queryKey: ['watchlist'],
    queryFn: apiClient.getWatchlist,
    enabled: !!entityId,
  });

  const { data: auditLogs = [], isLoading } = useQuery({
    queryKey: ['audit', entityId],
    queryFn: () => apiClient.getAudit(entityId),
    enabled: !!entityId,
  });

  const currentEntity = allEntities.find(e => e.id === entityId);

  if (!entityId) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-brand-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full space-y-6 max-w-5xl mx-auto w-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100 flex items-center gap-2">
            <History className="w-6 h-6 text-brand-400" />
            Immutable Audit Trail
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Cryptographically verifiable sequence of system actions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Entity selector */}
          {allEntities.length > 0 && (
            <select
              value={entityId}
              onChange={(e) => navigate(`/audit/${e.target.value}`)}
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-slate-200 focus:border-brand-500 outline-none"
            >
              {allEntities.map(e => (
                <option key={e.id} value={e.id}>{e.name}</option>
              ))}
            </select>
          )}
          <ChainVerifyBadge />
        </div>
      </div>

      {/* Entity context banner */}
      {currentEntity && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg px-4 py-3 flex items-center gap-4">
          <span className="text-xs text-slate-500 font-mono">{currentEntity.id}</span>
          <span className="text-slate-300 font-medium">{currentEntity.name}</span>
          <span className={`ml-auto text-xs font-semibold px-2 py-0.5 rounded-full border ${
            currentEntity.risk_band === 'CRITICAL' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
            currentEntity.risk_band === 'HIGH' ? 'bg-orange-500/10 text-orange-400 border-orange-500/20' :
            'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
          }`}>
            Risk: {currentEntity.risk_band} ({currentEntity.risk_score})
          </span>
        </div>
      )}

      <div className="bg-slate-900 border border-slate-800 rounded-xl flex-1 overflow-hidden flex flex-col">
        {isLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="w-8 h-8 text-brand-400 animate-spin" />
          </div>
        ) : auditLogs.length === 0 ? (
          <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
            No audit log entries for this entity yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm whitespace-nowrap font-mono">
              <thead className="bg-slate-800/50 text-slate-400">
                <tr>
                  <th className="px-6 py-4 font-medium">Seq</th>
                  <th className="px-6 py-4 font-medium">Time (UTC)</th>
                  <th className="px-6 py-4 font-medium">Actor</th>
                  <th className="px-6 py-4 font-medium">Action</th>
                  <th className="px-6 py-4 font-medium">Prev Hash</th>
                  <th className="px-6 py-4 font-medium">Entry Hash</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {auditLogs.map((entry, idx) => (
                  <tr key={entry.id} className="hover:bg-slate-800/30">
                    <td className="px-6 py-4 text-brand-400">{entry.seq}</td>
                    <td className="px-6 py-4 text-slate-400 text-xs">
                      {new Date(entry.created_at || entry.timestamp).toISOString().replace('T', ' ').substring(0, 19)}
                    </td>
                    <td className="px-6 py-4 text-slate-300">
                      <span className={entry.actor === 'human' ? 'text-emerald-400' : 'text-purple-400'}>
                        {entry.actor}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-200 font-bold text-xs">{entry.action}</td>
                    <td className="px-6 py-4 text-slate-500 text-xs">
                      {idx === 0 ? (
                        <span className="opacity-50">{entry.prev_hash || entry.previous_hash}</span>
                      ) : (
                        <span className="text-green-500/70">← {(entry.prev_hash || entry.previous_hash || '').substring(0, 8)}</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-slate-400 text-xs">
                      {entry.entry_hash}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
