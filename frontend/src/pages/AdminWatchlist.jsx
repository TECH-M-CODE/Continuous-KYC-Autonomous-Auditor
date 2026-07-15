import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ShieldAlert, Zap, Search, ToggleLeft, ToggleRight, Loader2, X, TrendingUp } from 'lucide-react';
import { StatusBadge } from '../components/StatusBadge';
import { DetectionHealth } from '../components/DetectionHealth';
import { apiClient } from '../api/client';
import clsx from 'clsx';

const BAND_BAR = {
  CRITICAL: '#ef4444',
  HIGH:     '#f97316',
  MEDIUM:   '#eab308',
  LOW:      '#22c55e',
};

export const AdminWatchlist = () => {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [injectModalOpen, setInjectModalOpen] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState(null);
  const [injectForm, setInjectForm] = useState({ event_type: 'adverse_media', title: '', text: '' });

  const { data: entities = [], isLoading } = useQuery({
    queryKey: ['watchlist'],
    queryFn: apiClient.getWatchlist,
  });

  const injectMutation = useMutation({
    mutationFn: apiClient.injectEvent,
    onSuccess: () => {
      setInjectModalOpen(false);
      setInjectForm({ event_type: 'adverse_media', title: '', text: '' });
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-alerts'] });
    },
  });

  const openInjectModal = (entity) => {
    setSelectedEntity(entity);
    setInjectForm({
      event_type: 'adverse_media',
      title: `Risk signal detected for ${entity.name}`,
      text: `Automated system flagged ${entity.name} for compliance review.`,
    });
    setInjectModalOpen(true);
  };

  const handleInjectSubmit = (e) => {
    e.preventDefault();
    injectMutation.mutate({ ...injectForm, entity_hint: selectedEntity.name });
  };

  // Client-side search filter
  const filtered = useMemo(() => {
    if (!search.trim()) return entities;
    const q = search.toLowerCase();
    return entities.filter(e =>
      e.name?.toLowerCase().includes(q) ||
      e.id?.toLowerCase().includes(q) ||
      e.type?.toLowerCase().includes(q) ||
      e.jurisdiction?.toLowerCase().includes(q)
    );
  }, [entities, search]);

  return (
    <div className="flex flex-col h-full space-y-5 max-w-7xl mx-auto w-full relative">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <ShieldAlert className="w-6 h-6 text-brand-400" />
            Admin Watchlist
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">Monitor entities and inject synthetic events for testing.</p>
        </div>
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by name, ID, type…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-9 pr-4 py-2 rounded-xl border border-slate-700 bg-slate-900/60 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-brand-500/60 w-64 transition-colors"
          />
          {search && (
            <button onClick={() => setSearch('')} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      <div className="flex gap-5 flex-1 overflow-hidden">
        {/* Table */}
        <div className="glass-card rounded-2xl flex-1 overflow-hidden flex flex-col">
          {isLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="w-7 h-7 text-brand-400 animate-spin" />
            </div>
          ) : (
            <>
              <div className="px-5 py-3 border-b border-slate-800/60 flex items-center justify-between">
                <span className="text-xs text-slate-500">
                  {filtered.length} of {entities.length} entities
                  {search && ` matching "${search}"`}
                </span>
                <div className="flex items-center gap-1 text-xs text-slate-600">
                  <TrendingUp className="w-3.5 h-3.5" />
                  Sorted by risk score
                </div>
              </div>
              <div className="overflow-x-auto overflow-y-auto flex-1">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-800/60 sticky top-0 bg-slate-900/90 backdrop-blur-sm">
                    <tr className="text-xs text-slate-500 uppercase tracking-wider">
                      <th className="px-5 py-3">Entity</th>
                      <th className="px-5 py-3">Type</th>
                      <th className="px-5 py-3">Risk</th>
                      <th className="px-5 py-3">Score</th>
                      <th className="px-5 py-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...filtered]
                      .sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0))
                      .map(entity => {
                        const barColor = BAND_BAR[entity.risk_band] || '#64748b';
                        return (
                          <tr key={entity.id} className="border-b border-slate-800/40 hover:bg-slate-800/20 transition-colors group">
                            <td className="px-5 py-3">
                              <Link to={`/timeline/${entity.id}`} className="font-medium text-slate-200 hover:text-brand-300 transition-colors group-hover:text-brand-300">
                                {entity.name}
                              </Link>
                              <p className="text-xs text-slate-600 font-mono mt-0.5">{entity.id}</p>
                            </td>
                            <td className="px-5 py-3 text-sm text-slate-400">{entity.type}</td>
                            <td className="px-5 py-3">
                              <StatusBadge band={entity.risk_band?.toLowerCase() || 'low'} />
                            </td>
                            <td className="px-5 py-3">
                              <div className="flex items-center gap-2.5">
                                <div className="w-20 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                                  <div
                                    className="h-1.5 rounded-full transition-all"
                                    style={{ width: `${entity.risk_score || 0}%`, background: barColor }}
                                  />
                                </div>
                                <span className="text-xs font-bold font-mono w-8" style={{ color: barColor }}>
                                  {entity.risk_score ?? '—'}
                                </span>
                              </div>
                            </td>
                            <td className="px-5 py-3 text-right">
                              <button
                                onClick={() => openInjectModal(entity)}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-purple-500/20 bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 text-xs font-medium transition-all"
                              >
                                <Zap className="w-3 h-3" /> Inject
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    {filtered.length === 0 && (
                      <tr>
                        <td colSpan="5" className="px-5 py-12 text-center text-slate-600 text-sm">
                          {search ? `No entities match "${search}"` : 'No entities found.'}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>

        {/* Sidebar */}
        <div className="w-72 shrink-0">
          <DetectionHealth />
        </div>
      </div>

      {/* ── Inject Modal ── */}
      {injectModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md">
          <div className="glass-card border-brand-500/20 rounded-2xl shadow-2xl w-full max-w-md p-6 animate-slide-up">
            <div className="flex justify-between items-center mb-5">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Zap className="w-5 h-5 text-purple-400" />
                Inject Demo Event
              </h3>
              <button onClick={() => setInjectModalOpen(false)} className="text-slate-500 hover:text-slate-200 transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleInjectSubmit} className="space-y-4">
              <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700 text-sm">
                <p className="text-xs text-slate-500 mb-1">Target Entity</p>
                <p className="text-slate-200 font-medium">{selectedEntity?.name}</p>
                <p className="text-xs text-slate-500 font-mono mt-0.5">{selectedEntity?.id}</p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Event Type</label>
                <select
                  value={injectForm.event_type}
                  onChange={e => setInjectForm({ ...injectForm, event_type: e.target.value })}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-slate-200 focus:border-brand-500 outline-none"
                >
                  <option value="adverse_media">Adverse Media</option>
                  <option value="transaction_anomaly">Transaction Anomaly</option>
                  <option value="sanctions_hit">Sanctions List Hit</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Event Title</label>
                <input
                  type="text"
                  value={injectForm.title}
                  onChange={e => setInjectForm({ ...injectForm, title: e.target.value })}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-slate-200 focus:border-brand-500 outline-none"
                  placeholder="e.g. Adverse media: fraud allegation"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Event Details</label>
                <textarea
                  value={injectForm.text}
                  onChange={e => setInjectForm({ ...injectForm, text: e.target.value })}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-slate-200 focus:border-brand-500 outline-none h-20 resize-none"
                  placeholder="Describe the risk event in detail…"
                  required
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setInjectModalOpen(false)}
                  className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200 transition-colors">
                  Cancel
                </button>
                <button type="submit" disabled={injectMutation.isPending}
                  className="flex items-center gap-2 px-5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-sm font-semibold transition-colors disabled:opacity-50">
                  {injectMutation.isPending
                    ? <><Loader2 className="w-4 h-4 animate-spin" /> Injecting…</>
                    : <><Zap className="w-4 h-4" /> Inject Event</>}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
