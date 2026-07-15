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
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2 drop-shadow-sm">
            <History className="w-6 h-6 text-brand-500" />
            Immutable Audit Trail
          </h1>
          <p className="text-sm text-slate-500 mt-1 font-medium">
            Cryptographically verifiable sequence of system actions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Entity selector */}
          {allEntities.length > 0 && (
            <select
              value={entityId}
              onChange={(e) => navigate(`/audit/${e.target.value}`)}
              className="glass-input px-3 py-1.5 text-sm text-slate-800 font-semibold"
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
        <div className="glass-panel px-5 py-3 flex items-center gap-4">
          <span className="text-xs text-slate-500 font-mono font-medium">{currentEntity.id}</span>
          <span className="text-slate-800 font-bold">{currentEntity.name}</span>
          <span className={`ml-auto text-xs font-bold px-3 py-1 rounded-full border shadow-sm ${
            currentEntity.risk_band === 'CRITICAL' ? 'bg-red-100 text-red-600 border-red-200' :
            currentEntity.risk_band === 'HIGH' ? 'bg-orange-100 text-orange-600 border-orange-200' :
            'bg-emerald-100 text-emerald-600 border-emerald-200'
          }`}>
            Risk: {currentEntity.risk_band} ({currentEntity.risk_score})
          </span>
        </div>
      )}

      <div className="glass-panel flex-1 overflow-hidden flex flex-col">
        {isLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
          </div>
        ) : auditLogs.length === 0 ? (
          <div className="flex-1 flex items-center justify-center text-slate-500 text-sm font-semibold">
            No audit log entries for this entity yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm whitespace-nowrap font-mono">
              <thead className="bg-white/40 text-slate-600 border-b border-white/50 backdrop-blur-sm">
                <tr>
                  <th className="px-6 py-4 font-bold">Seq</th>
                  <th className="px-6 py-4 font-bold">Time (UTC)</th>
                  <th className="px-6 py-4 font-bold">Actor</th>
                  <th className="px-6 py-4 font-bold">Action</th>
                  <th className="px-6 py-4 font-bold">Prev Hash</th>
                  <th className="px-6 py-4 font-bold">Entry Hash</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/40">
                {auditLogs.map((entry, idx) => (
                  <tr key={entry.id} className="hover:bg-white/40 transition-colors">
                    <td className="px-6 py-4 text-brand-600 font-bold">{entry.seq}</td>
                    <td className="px-6 py-4 text-slate-500 text-xs font-semibold">
                      {new Date(entry.created_at || entry.timestamp).toISOString().replace('T', ' ').substring(0, 19)}
                    </td>
                    <td className="px-6 py-4 text-slate-700 font-bold">
                      <span className={entry.actor === 'human' ? 'text-emerald-600' : 'text-purple-600'}>
                        {entry.actor}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-800 font-bold text-xs">{entry.action}</td>
                    <td className="px-6 py-4 text-slate-500 text-xs font-medium">
                      {idx === 0 ? (
                        <span className="opacity-50">{entry.prev_hash || entry.previous_hash}</span>
                      ) : (
                        <span className="text-emerald-600">← {(entry.prev_hash || entry.previous_hash || '').substring(0, 8)}</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-slate-500 text-xs font-medium">
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
