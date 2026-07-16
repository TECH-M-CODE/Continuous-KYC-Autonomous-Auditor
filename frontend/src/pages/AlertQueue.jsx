import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useSSE } from '../hooks/useSSE';
import { StatusBadge } from '../components/StatusBadge';
import {
  Shield, Check, X, Filter, GitMerge, Loader2,
  Activity, ChevronDown, ChevronUp, Bell
} from 'lucide-react';
import { apiClient } from '../api/client';
import clsx from 'clsx';

const PRIORITY_STYLE = {
  CRITICAL: { border: 'border-l-red-500',    dot: 'bg-red-400',    glow: 'shadow-red-500/10' },
  HIGH:     { border: 'border-l-orange-500', dot: 'bg-orange-400', glow: 'shadow-orange-500/10' },
  MEDIUM:   { border: 'border-l-yellow-500', dot: 'bg-yellow-400', glow: 'shadow-yellow-500/10' },
  LOW:      { border: 'border-l-emerald-500',dot: 'bg-emerald-400',glow: 'shadow-emerald-500/10' },
};

const timeAgo = (iso, now = Date.now()) => {
  const d = Math.floor((now - new Date(iso)) / 60000);
  if (d < 1) return 'just now';
  if (d < 60) return `${d}m ago`;
  return `${Math.floor(d / 60)}h ago`;
};

export const AlertQueue = () => {
  const { lastEvent } = useSSE();
  const [filter, setFilter] = useState('all');
  const [toast, setToast] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 60000);
    return () => clearInterval(timer);
  }, []);

  const { data: alerts = [], isLoading } = useQuery({
    queryKey: ['alerts'],
    queryFn: apiClient.getAlerts,
    refetchInterval: 10_000,
    // Keep the current rows on screen while a refetch (triggered by an incoming
    // SSE alert) is in flight — prevents the table from blanking for a beat.
    placeholderData: keepPreviousData,
  });

  const queryClient = useQueryClient();
  const actionMutation = useMutation({
    mutationFn: apiClient.actionAlert,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
  });

  const handleAction = (id, action) =>
    actionMutation.mutate({ id, action, reasoning: `Manual ${action} by reviewer` });

  const handleBulkAction = (action) => {
    selected.forEach(id => actionMutation.mutate({ id, action, reasoning: `Bulk ${action}` }));
    setSelected(new Set());
  };

  useEffect(() => {
    if (lastEvent?.type === 'alert.new') {
      setToast(lastEvent.data);
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      const t = setTimeout(() => setToast(null), 6000);
      return () => clearTimeout(t);
    }
  }, [lastEvent, queryClient]);

  const FILTERS = ['all', 'critical', 'high', 'medium', 'low'];
  // Only alerts that still need attention stay in the queue. Dismissing an alert
  // (or approving/rejecting its SAR) resolves it, which removes it from here.
  const activeAlerts = alerts.filter(
    a => !['DISMISSED', 'RESOLVED'].includes((a.status || '').toUpperCase())
  );
  const filteredAlerts = activeAlerts.filter(a =>
    filter === 'all' || a.priority?.toLowerCase() === filter
  );

  // Count per band for filter tabs
  const countByBand = FILTERS.reduce((acc, f) => {
    acc[f] = f === 'all' ? activeAlerts.length : activeAlerts.filter(a => a.priority?.toLowerCase() === f).length;
    return acc;
  }, {});

  const toggleSelect = (id) => {
    setSelected(prev => {
      const n = new Set(prev);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  };

  return (
    <div className="flex flex-col h-full space-y-5 max-w-7xl mx-auto w-full relative">

      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -40, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.95 }}
            className="absolute top-0 left-1/2 -translate-x-1/2 z-50 glass-card border border-red-500/30 shadow-2xl rounded-2xl p-4 flex items-start gap-3 min-w-[340px]"
          >
            <div className="p-2 bg-red-500/20 rounded-xl shrink-0">
              <Shield className="w-4 h-4 text-red-400" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold text-white">New {toast.priority} Alert</p>
              <p className="text-xs text-slate-400 mt-0.5">{toast.entity_name || toast.entity_id} — {toast.status}</p>
            </div>
            <button onClick={() => setToast(null)} className="text-slate-500 hover:text-slate-300 mt-0.5">
              <X className="w-3.5 h-3.5" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <Bell className="w-6 h-6 text-brand-400" />
            Alert Queue
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">Review and triage incoming risk alerts.</p>
        </div>

        {/* Bulk actions */}
        {selected.size > 0 && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-brand-500/30 bg-brand-500/5 text-xs">
            <span className="text-brand-400 font-medium">{selected.size} selected</span>
            <button onClick={() => handleBulkAction('DISMISS')}
              className="px-2 py-1 rounded-lg bg-slate-800 hover:bg-emerald-500/20 text-emerald-400 transition-colors">
              Dismiss All
            </button>
            <button onClick={() => handleBulkAction('ESCALATE')}
              className="px-2 py-1 rounded-lg bg-slate-800 hover:bg-red-500/20 text-red-400 transition-colors">
              Escalate All
            </button>
            <button onClick={() => setSelected(new Set())} className="text-slate-500 hover:text-slate-300">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-1 p-1 rounded-xl border border-slate-800 bg-slate-900/50 w-fit">
        <Filter className="w-3.5 h-3.5 text-slate-600 ml-2 mr-1" />
        {FILTERS.map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={clsx(
              'px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-all',
              filter === f
                ? 'bg-brand-500/20 text-brand-300 border border-brand-500/30'
                : 'text-slate-500 hover:text-slate-300'
            )}
          >
            {f}
            {countByBand[f] > 0 && (
              <span className={clsx(
                'ml-1.5 px-1 py-0.5 rounded text-[10px] font-bold',
                filter === f ? 'text-brand-400' : 'text-slate-600'
              )}>
                {countByBand[f]}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="glass-card rounded-2xl flex-1 overflow-hidden flex flex-col">
        {isLoading && alerts.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="w-7 h-7 text-brand-400 animate-spin" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-800/80">
                <tr className="text-xs text-slate-500 uppercase tracking-wider">
                  <th className="px-4 py-3 w-8">
                    <input type="checkbox"
                      checked={selected.size === filteredAlerts.length && filteredAlerts.length > 0}
                      onChange={e => setSelected(e.target.checked ? new Set(filteredAlerts.map(a => a.id)) : new Set())}
                      className="accent-brand-500 cursor-pointer"
                    />
                  </th>
                  <th className="px-4 py-3">Entity</th>
                  <th className="px-4 py-3">Priority</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Time</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                <AnimatePresence initial={false}>
                  {filteredAlerts.map(alert => {
                    const style = PRIORITY_STYLE[alert.priority] || PRIORITY_STYLE.LOW;
                    const isExpanded = expanded === alert.id;

                    return (
                      <React.Fragment key={alert.id}>
                        <motion.tr
                          layout
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, x: 10 }}
                          className={clsx(
                            'border-l-2 border-b border-slate-800/50 hover:bg-slate-800/20 transition-all cursor-pointer group',
                            style.border,
                            selected.has(alert.id) && 'bg-brand-500/5'
                          )}
                          onClick={() => setExpanded(isExpanded ? null : alert.id)}
                        >
                          <td className="px-4 py-3" onClick={e => e.stopPropagation()}>
                            <input type="checkbox"
                              checked={selected.has(alert.id)}
                              onChange={() => toggleSelect(alert.id)}
                              className="accent-brand-500 cursor-pointer"
                            />
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <div className={clsx('w-1.5 h-1.5 rounded-full shrink-0', style.dot)} />
                              <div>
                                <p className="font-medium text-slate-200 group-hover:text-brand-300 transition-colors">
                                  {alert.entity_name || alert.entity_id}
                                </p>
                                <p className="text-xs text-slate-600 font-mono">{alert.id?.slice(0, 12)}…</p>
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-3"><StatusBadge band={alert.priority?.toLowerCase()} /></td>
                          <td className="px-4 py-3">
                            <span className={clsx(
                              'text-xs px-2 py-0.5 rounded-full border font-medium',
                              alert.status === 'OPEN'
                                ? 'text-amber-400 bg-amber-500/10 border-amber-500/20'
                                : 'text-slate-400 bg-slate-800 border-slate-700'
                            )}>{alert.status}</span>
                          </td>
                          <td className="px-4 py-3 text-xs text-slate-500">
                            {timeAgo(alert.created_at, now)}
                          </td>
                          <td className="px-4 py-3 text-right" onClick={e => e.stopPropagation()}>
                            <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                              <Link
                                to={`/alerts/${alert.id}/trace`}
                                className="flex items-center gap-1 px-2 py-1 bg-slate-800 hover:bg-brand-500/20 text-brand-400 border border-slate-700 hover:border-brand-500/50 rounded-lg text-xs font-semibold transition-colors"
                              >
                                <GitMerge className="w-3 h-3" /> Why?
                              </Link>
                              <button onClick={() => handleAction(alert.id, 'DISMISS')}
                                title="Dismiss — clear this alert and remove it from the queue"
                                className="p-1.5 text-slate-500 hover:text-emerald-400 hover:bg-emerald-400/10 rounded-lg transition-colors">
                                <Check className="w-4 h-4" />
                              </button>
                              <button onClick={() => handleAction(alert.id, 'ESCALATE')}
                                title="Escalate — flag for senior (MLRO) review"
                                className="p-1.5 text-slate-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors">
                                <Shield className="w-4 h-4" />
                              </button>
                              <button
                                title={isExpanded ? 'Hide details' : 'Show details'}
                                onClick={() => setExpanded(isExpanded ? null : alert.id)}
                                className="p-1.5 text-slate-600 hover:text-slate-300 transition-colors">
                                {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                              </button>
                            </div>
                          </td>
                        </motion.tr>

                        {/* Expanded details */}
                        <AnimatePresence>
                          {isExpanded && (
                            <motion.tr
                              initial={{ opacity: 0 }}
                              animate={{ opacity: 1 }}
                              exit={{ opacity: 0 }}
                            >
                              <td colSpan="6" className="px-6 pb-4 bg-slate-900/40">
                                <div className="rounded-xl border border-slate-800 p-4 mt-1">
                                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs mb-3">
                                    <div>
                                      <p className="text-slate-500 mb-1">Entity ID</p>
                                      <p className="font-mono text-slate-300">{alert.entity_id || '—'}</p>
                                    </div>
                                    <div>
                                      <p className="text-slate-500 mb-1">Risk Score</p>
                                      <p className="font-bold text-slate-200">{alert.risk_score ?? '—'}</p>
                                    </div>
                                    <div>
                                      <p className="text-slate-500 mb-1">Created</p>
                                      <p className="text-slate-300">{new Date(alert.created_at).toLocaleString()}</p>
                                    </div>
                                    <div>
                                      <p className="text-slate-500 mb-1">Source</p>
                                      <p className="text-slate-300">{alert.source || '—'}</p>
                                    </div>
                                  </div>
                                  {alert.summary && (
                                    <p className="text-xs text-slate-400 leading-relaxed border-t border-slate-800 pt-3">{alert.summary}</p>
                                  )}
                                  <div className="flex gap-2 mt-3">
                                    <Link
                                      to={`/timeline/${alert.entity_id}`}
                                      className="text-xs text-brand-400 hover:text-brand-300 flex items-center gap-1 transition-colors"
                                    >
                                      <Activity className="w-3 h-3" /> View Entity Timeline →
                                    </Link>
                                  </div>
                                </div>
                              </td>
                            </motion.tr>
                          )}
                        </AnimatePresence>
                      </React.Fragment>
                    );
                  })}
                </AnimatePresence>
                {filteredAlerts.length === 0 && (
                  <tr>
                    <td colSpan="6" className="px-6 py-16 text-center text-slate-600 text-sm">
                      No alerts in this queue.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
