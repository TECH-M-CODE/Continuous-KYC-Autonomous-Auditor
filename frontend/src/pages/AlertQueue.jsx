import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useSSE } from '../hooks/useSSE';
import { StatusBadge } from '../components/StatusBadge';
import { Shield, Check, X, Filter, GitMerge, Loader2, Activity } from 'lucide-react';
import { apiClient } from '../api/client';

export const AlertQueue = () => {
  const { lastEvent } = useSSE();
  const [filter, setFilter] = useState('all');
  const [toast, setToast] = useState(null);

  const { data: alerts = [], isLoading } = useQuery({
    queryKey: ['alerts'],
    queryFn: apiClient.getAlerts,
  });

  const queryClient = useQueryClient();

  const actionMutation = useMutation({
    mutationFn: apiClient.actionAlert,
    onSuccess: () => {
      queryClient.invalidateQueries(['alerts']);
    }
  });

  const handleAction = (id, action) => {
    actionMutation.mutate({ id, action, reasoning: `Manual ${action} by reviewer` });
  };

  useEffect(() => {
    if (lastEvent?.type === 'alert.new') {
      const newAlert = lastEvent.data;
      setToast(newAlert);
      const timer = setTimeout(() => setToast(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [lastEvent]);

  const filteredAlerts = alerts.filter(a => filter === 'all' || a.priority?.toLowerCase() === filter);

  return (
    <div className="flex flex-col h-full space-y-6">
      {/* Toast Notification */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -50, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.9 }}
            className="absolute top-6 left-1/2 transform -translate-x-1/2 z-50 bg-slate-800 border border-slate-700 shadow-2xl rounded-xl p-4 flex items-start gap-4 min-w-[320px]"
          >
            <div className="mt-1 bg-red-500/20 p-2 rounded-full">
              <Shield className="w-5 h-5 text-red-400" />
            </div>
            <div className="flex-1">
              <h4 className="text-sm font-semibold text-slate-100">New {toast.priority} Alert</h4>
              <p className="text-xs text-slate-400 mt-1">{toast.entity_name} — {toast.status}</p>
            </div>
            <button onClick={() => setToast(null)} className="text-slate-500 hover:text-slate-300">
              <X className="w-4 h-4" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">Alert Queue</h1>
          <p className="text-sm text-slate-400 mt-1">Review and triage incoming risk alerts.</p>
        </div>
        
        {/* Filters */}
        <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 rounded-lg p-1">
          <Filter className="w-4 h-4 text-slate-500 ml-2 mr-1" />
          {['all', 'critical', 'high', 'medium'].map(band => (
            <button
              key={band}
              onClick={() => setFilter(band)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium capitalize transition-colors ${
                filter === band ? 'bg-slate-800 text-slate-200' : 'text-slate-400 hover:text-slate-300 hover:bg-slate-800/50'
              }`}
            >
              {band}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl flex-1 overflow-hidden flex flex-col">
        {isLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="w-8 h-8 text-brand-400 animate-spin" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="bg-slate-800/50 text-slate-400">
                <tr>
                  <th className="px-6 py-4 font-medium">Entity</th>
                  <th className="px-6 py-4 font-medium">Priority</th>
                  <th className="px-6 py-4 font-medium">Status</th>
                  <th className="px-6 py-4 font-medium">Time (UTC)</th>
                  <th className="px-6 py-4 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                <AnimatePresence initial={false}>
                  {filteredAlerts.map(alert => (
                    <motion.tr 
                      key={alert.id}
                      layout
                      initial={{ opacity: 0, backgroundColor: 'rgba(59, 130, 246, 0.1)' }}
                      animate={{ opacity: 1, backgroundColor: 'transparent' }}
                      exit={{ opacity: 0, x: -20 }}
                      transition={{ duration: 0.3 }}
                      className="hover:bg-slate-800/20 group"
                    >
                      <td className="px-6 py-4">
                        <Link
                          to={`/timeline/${alert.entity_id || ''}`}
                          className="font-medium text-slate-200 hover:text-brand-400 transition-colors flex items-center gap-1.5"
                        >
                          <Activity className="w-3.5 h-3.5 text-slate-500" />
                          {alert.entity_name || alert.entity_id}
                        </Link>
                        <div className="text-xs text-slate-500 font-mono mt-0.5">{alert.id}</div>
                      </td>
                      <td className="px-6 py-4">
                        <StatusBadge band={alert.priority?.toLowerCase()} />
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-slate-400">{alert.status}</span>
                      </td>
                      <td className="px-6 py-4 text-slate-400 text-xs">
                        {new Date(alert.created_at).toLocaleTimeString()}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <Link 
                            to={`/alerts/${alert.id}/trace`}
                            className="flex items-center gap-1 px-3 py-1.5 bg-slate-800 hover:bg-brand-500/20 text-brand-400 border border-slate-700 hover:border-brand-500/50 rounded-md transition-colors text-xs font-semibold mr-2"
                          >
                            <GitMerge className="w-3.5 h-3.5" />
                            Why?
                          </Link>
                          <button 
                            onClick={() => handleAction(alert.id, 'DISMISS')}
                            disabled={actionMutation.isPending}
                            className="p-1.5 text-slate-400 hover:text-green-400 hover:bg-green-400/10 rounded-md transition-colors" title="Dismiss">
                            <Check className="w-4 h-4" />
                          </button>
                          <button 
                            onClick={() => handleAction(alert.id, 'ESCALATE')}
                            disabled={actionMutation.isPending}
                            className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-400/10 rounded-md transition-colors" title="Escalate">
                            <Shield className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </motion.tr>
                  ))}
                </AnimatePresence>
                
                {filteredAlerts.length === 0 && (
                  <tr>
                    <td colSpan="5" className="px-6 py-12 text-center text-slate-500">
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
