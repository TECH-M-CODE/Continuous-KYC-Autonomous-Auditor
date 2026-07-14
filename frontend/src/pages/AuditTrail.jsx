import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { History, Loader2 } from 'lucide-react';
import { apiClient } from '../api/client';
import { ChainVerifyBadge } from '../components/ChainVerifyBadge';

export const AuditTrail = () => {
  const { data: auditLogs = [], isLoading } = useQuery({
    queryKey: ['audit'],
    queryFn: apiClient.getAudit
  });

  return (
    <div className="flex flex-col h-full space-y-6 max-w-5xl mx-auto w-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100 flex items-center gap-2">
            <History className="w-6 h-6 text-brand-400" />
            Immutable Audit Trail
          </h1>
          <p className="text-sm text-slate-400 mt-1">Cryptographically verifiable sequence of system actions.</p>
        </div>
        
        <ChainVerifyBadge />
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl flex-1 overflow-hidden flex flex-col">
        {isLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="w-8 h-8 text-brand-400 animate-spin" />
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
                      {new Date(entry.created_at).toISOString().replace('T', ' ').substring(0, 19)}
                    </td>
                    <td className="px-6 py-4 text-slate-300">
                      <span className={entry.actor.includes('System') ? 'text-purple-400' : 'text-emerald-400'}>
                        {entry.actor}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-200 font-bold text-xs">{entry.action}</td>
                    <td className="px-6 py-4 text-slate-500 text-xs">
                      {idx === 0 ? (
                        <span className="opacity-50">{entry.prev_hash}</span>
                      ) : (
                        <span className="text-green-500/70">← {entry.prev_hash.substring(0, 8)}</span>
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
