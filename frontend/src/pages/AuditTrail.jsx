import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { History, Loader2, ShieldCheck, ShieldX, Download } from 'lucide-react';
import { apiClient } from '../api/client';
import { ChainVerifyBadge } from '../components/ChainVerifyBadge';
import { HashChain } from '../components/HashChain';
import { EntitySelector } from '../components/EntitySelector';
import clsx from 'clsx';

export const AuditTrail = () => {
  const { entityId } = useParams();
  const navigate = useNavigate();

  const { data: allEntities = [] } = useQuery({
    queryKey: ['watchlist'],
    queryFn: apiClient.getWatchlist,
  });

  const { data: auditLogs = [], isLoading } = useQuery({
    queryKey: ['audit', entityId],
    queryFn: () => apiClient.getAudit(entityId),
    enabled: !!entityId,
  });

  const { data: auditStatus } = useQuery({
    queryKey: ['dashboard-audit-verify'],
    queryFn: apiClient.verifyAuditChain,
  });

  const currentEntity = allEntities.find(e => e.id === entityId);

  // Export CSV
  const handleExport = () => {
    if (!auditLogs.length) return;
    const header = ['seq', 'timestamp', 'actor', 'action', 'prev_hash', 'entry_hash'];
    const rows = auditLogs.map(e => [
      e.seq, e.created_at || e.timestamp, e.actor, e.action,
      e.prev_hash || e.previous_hash, e.entry_hash
    ]);
    const csv = [header, ...rows].map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit-${entityId}-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex h-full gap-5 max-w-7xl mx-auto w-full">

      {/* ── Left: Entity Selector ── */}
      <div className="w-56 shrink-0 glass-card rounded-2xl p-3 flex flex-col overflow-hidden">
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 px-1">
          Entities
        </h2>
        <EntitySelector basePath="/audit" selectedId={entityId} />
      </div>

      {/* ── Right: Audit detail ── */}
      <div className="flex-1 flex flex-col space-y-4 overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
              <History className="w-6 h-6 text-brand-400" />
              Immutable Audit Trail
            </h1>
            <p className="text-sm text-slate-500 mt-0.5">Cryptographically verifiable action sequence.</p>
          </div>
          <div className="flex items-center gap-3">
            <ChainVerifyBadge />
            {auditLogs.length > 0 && (
              <button
                onClick={handleExport}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-700 bg-slate-800/50 hover:bg-slate-700/50 text-xs text-slate-300 hover:text-white transition-all"
              >
                <Download className="w-3.5 h-3.5" />
                Export CSV
              </button>
            )}
          </div>
        </div>

        {/* Chain integrity banner */}
        {auditStatus && (
          <div className={clsx(
            'flex items-center gap-3 px-4 py-3 rounded-xl border text-sm font-medium',
            auditStatus.is_valid
              ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-400'
              : 'bg-red-500/5 border-red-500/20 text-red-400'
          )}>
            {auditStatus.is_valid
              ? <ShieldCheck className="w-5 h-5 shrink-0" />
              : <ShieldX className="w-5 h-5 shrink-0" />}
            <span>
              {auditStatus.is_valid
                ? `✓ Chain integrity verified — ${auditStatus.total_entries ?? auditLogs.length} entries, no tampering detected`
                : '⚠ Chain integrity compromised — hash mismatch detected'}
            </span>
          </div>
        )}

        {/* Entity context */}
        {currentEntity && (
          <div className="glass-card rounded-xl px-4 py-2.5 flex items-center gap-4">
            <span className="text-xs font-mono text-slate-500">{currentEntity.id}</span>
            <span className="text-sm font-semibold text-slate-200">{currentEntity.name}</span>
            <span className={clsx(
              'ml-auto text-xs font-semibold px-2 py-0.5 rounded-full border',
              currentEntity.risk_band === 'CRITICAL' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
              currentEntity.risk_band === 'HIGH'     ? 'bg-orange-500/10 text-orange-400 border-orange-500/20' :
              'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
            )}>
              Risk: {currentEntity.risk_band} ({currentEntity.risk_score})
            </span>
          </div>
        )}

        {/* Chain */}
        <div className="glass-card rounded-2xl flex-1 overflow-y-auto p-5">
          {!entityId && (
            <div className="flex h-48 items-center justify-center text-slate-600 text-sm">
              ← Select an entity to view its audit trail
            </div>
          )}
          {entityId && isLoading && (
            <div className="flex h-48 items-center justify-center">
              <Loader2 className="w-7 h-7 text-brand-400 animate-spin" />
            </div>
          )}
          {entityId && !isLoading && auditLogs.length === 0 && (
            <div className="flex h-48 items-center justify-center text-slate-600 text-sm">
              No audit entries for this entity yet.
            </div>
          )}
          {auditLogs.length > 0 && (
            <HashChain entries={auditLogs} isValid={auditStatus?.is_valid ?? true} />
          )}
        </div>
      </div>
    </div>
  );
};
