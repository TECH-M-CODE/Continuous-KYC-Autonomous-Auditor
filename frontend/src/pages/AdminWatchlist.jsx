import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ShieldAlert, Zap, Search, ToggleLeft, ToggleRight, Loader2, X } from 'lucide-react';
import { StatusBadge } from '../components/StatusBadge';
import { DetectionHealth } from '../components/DetectionHealth';
import { apiClient } from '../api/client';

export const AdminWatchlist = () => {
  const queryClient = useQueryClient();
  const [injectModalOpen, setInjectModalOpen] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState(null);
  const [injectForm, setInjectForm] = useState({ event_type: 'adverse_media', severity: 'high' });

  const { data: entities = [], isLoading } = useQuery({
    queryKey: ['watchlist'],
    queryFn: apiClient.getWatchlist
  });

  const injectMutation = useMutation({
    mutationFn: apiClient.injectEvent,
    onSuccess: () => {
      setInjectModalOpen(false);
      // In a real scenario, this would eventually trigger SSE `alert.new`
      // which invalidates the alerts query.
    }
  });

  const toggleWatch = (id) => {
    // Optimistic or real mutation goes here in Sprint 3
    console.log("Toggle watch", id);
  };

  const openInjectModal = (entity) => {
    setSelectedEntity(entity);
    setInjectForm({ event_type: 'adverse_media', severity: 'high' });
    setInjectModalOpen(true);
  };

  const handleInjectSubmit = (e) => {
    e.preventDefault();
    injectMutation.mutate({
      entity_id: selectedEntity.id,
      ...injectForm
    });
  };

  return (
    <div className="flex flex-col h-full space-y-6 max-w-7xl mx-auto w-full relative">
      <div className="flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100 flex items-center gap-2">
            <ShieldAlert className="w-6 h-6 text-brand-400" />
            Admin Watchlist & Testing
          </h1>
          <p className="text-sm text-slate-400 mt-1">Manage entity monitoring and trigger synthetic events for demo.</p>
        </div>
        
        <div className="relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input 
            type="text" 
            placeholder="Search entities..." 
            className="pl-9 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-brand-500 w-64"
          />
        </div>
      </div>

      <div className="flex gap-6 flex-1 overflow-hidden">
        {/* Main Table */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl flex-1 overflow-hidden flex flex-col">
          {isLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="w-8 h-8 text-brand-400 animate-spin" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="bg-slate-800/50 text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="px-6 py-4 font-medium">Entity</th>
                    <th className="px-6 py-4 font-medium">Type</th>
                    <th className="px-6 py-4 font-medium">Risk Band</th>
                    <th className="px-6 py-4 font-medium">Risk Score</th>
                    <th className="px-6 py-4 font-medium text-center">Watched</th>
                    <th className="px-6 py-4 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {entities.map(entity => (
                    <tr key={entity.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-6 py-4">
                        <div className="font-medium text-slate-200">{entity.name}</div>
                        <div className="text-xs text-slate-500 font-mono mt-0.5">{entity.id}</div>
                      </td>
                      <td className="px-6 py-4 text-slate-300">{entity.type}</td>
                      <td className="px-6 py-4">
                        <StatusBadge 
                          band={entity.risk_band?.toLowerCase() || 'medium'} 
                        />
                      </td>
                      <td className="px-6 py-4 font-mono text-slate-400">{entity.risk_score}</td>
                      <td className="px-6 py-4 text-center">
                        <button 
                          onClick={() => toggleWatch(entity.id)}
                          className={`inline-flex items-center justify-center transition-colors ${entity.watched ? 'text-brand-400' : 'text-slate-600'}`}
                        >
                          {entity.watched ? <ToggleRight className="w-8 h-8" /> : <ToggleLeft className="w-8 h-8" />}
                        </button>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button 
                          onClick={() => openInjectModal(entity)}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 border border-purple-500/20 rounded-md text-xs font-medium transition-colors"
                        >
                          <Zap className="w-3.5 h-3.5" />
                          Inject Event
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right Sidebar */}
        <div className="w-[320px] shrink-0">
          <DetectionHealth />
        </div>
      </div>

      {/* Inject Modal */}
      {injectModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 p-6 rounded-xl shadow-2xl w-full max-w-md">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                <Zap className="w-5 h-5 text-purple-400" />
                Inject Demo Event
              </h3>
              <button onClick={() => setInjectModalOpen(false)} className="text-slate-400 hover:text-slate-200">
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <form onSubmit={handleInjectSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1 uppercase tracking-wider">Target Entity</label>
                <div className="text-slate-200 bg-slate-800/50 p-2 rounded border border-slate-700">
                  {selectedEntity?.name} <span className="text-slate-500 text-xs ml-2">({selectedEntity?.id})</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1 uppercase tracking-wider">Event Type</label>
                <select 
                  value={injectForm.event_type}
                  onChange={(e) => setInjectForm({ ...injectForm, event_type: e.target.value })}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-sm text-slate-200 focus:border-brand-500 outline-none"
                >
                  <option value="adverse_media">Adverse Media</option>
                  <option value="transaction_anomaly">Transaction Anomaly</option>
                  <option value="sanctions_hit">Sanctions List Hit</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1 uppercase tracking-wider">Severity</label>
                <select 
                  value={injectForm.severity}
                  onChange={(e) => setInjectForm({ ...injectForm, severity: e.target.value })}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-sm text-slate-200 focus:border-brand-500 outline-none"
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>

              <div className="pt-4 flex justify-end gap-3">
                <button 
                  type="button" 
                  onClick={() => setInjectModalOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-slate-100 transition-colors"
                >
                  Cancel
                </button>
                <button 
                  type="submit"
                  disabled={injectMutation.isPending}
                  className="px-4 py-2 text-sm font-medium bg-purple-600 hover:bg-purple-500 text-white rounded-lg flex items-center gap-2 transition-colors disabled:opacity-50"
                >
                  {injectMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Inject Event'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

