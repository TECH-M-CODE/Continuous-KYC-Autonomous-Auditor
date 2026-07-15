import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ShieldAlert, Zap, Search, ToggleLeft, ToggleRight, Loader2, X } from 'lucide-react';
import { StatusBadge } from '../components/StatusBadge';
import { DetectionHealth } from '../components/DetectionHealth';
import { apiClient } from '../api/client';

export const AdminWatchlist = () => {
  const queryClient = useQueryClient();
  const [injectModalOpen, setInjectModalOpen] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState(null);
  const [injectForm, setInjectForm] = useState({
    event_type: 'adverse_media',
    title: '',
    text: '',
  });

  const { data: entities = [], isLoading } = useQuery({
    queryKey: ['watchlist'],
    queryFn: apiClient.getWatchlist
  });

  const injectMutation = useMutation({
    mutationFn: apiClient.injectEvent,
    onSuccess: () => {
      setInjectModalOpen(false);
      setInjectForm({ event_type: 'adverse_media', title: '', text: '' });
      // Invalidate alerts so the Alert Queue auto-refreshes
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-alerts'] });
    }
  });

  const toggleWatch = (id) => {
    // Optimistic or real mutation goes here in Sprint 3
    console.log("Toggle watch", id);
  };

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
    injectMutation.mutate({
      event_type: injectForm.event_type,
      title: injectForm.title,
      text: injectForm.text,
      entity_hint: selectedEntity.name,  // backend matches by name
    });
  };

  return (
    <div className="flex flex-col h-full space-y-6 max-w-7xl mx-auto w-full relative">
      <div className="flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2 drop-shadow-sm">
            <ShieldAlert className="w-6 h-6 text-brand-500" />
            Admin Watchlist & Testing
          </h1>
          <p className="text-sm text-slate-500 mt-1 font-medium">Manage entity monitoring and trigger synthetic events for demo.</p>
        </div>
        
        <div className="relative">
          <Search className="w-4 h-4 text-brand-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input 
            type="text" 
            placeholder="Search entities..." 
            className="pl-9 pr-4 py-2 glass-input text-sm text-slate-800 w-64 font-medium"
          />
        </div>
      </div>

      <div className="flex gap-6 flex-1 overflow-hidden">
        {/* Main Table */}
        <div className="glass-panel flex-1 overflow-hidden flex flex-col">
          {isLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="bg-white/40 text-slate-700 border-b border-white/50 backdrop-blur-sm">
                  <tr>
                    <th className="px-6 py-4 font-bold uppercase tracking-wider text-xs">Entity</th>
                    <th className="px-6 py-4 font-bold uppercase tracking-wider text-xs">Type</th>
                    <th className="px-6 py-4 font-bold uppercase tracking-wider text-xs">Risk Band</th>
                    <th className="px-6 py-4 font-bold uppercase tracking-wider text-xs">Risk Score</th>
                    <th className="px-6 py-4 font-bold uppercase tracking-wider text-xs text-center">Watched</th>
                    <th className="px-6 py-4 font-bold uppercase tracking-wider text-xs text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/40">
                  {entities.map(entity => (
                    <tr key={entity.id} className="hover:bg-white/40 transition-colors">
                      <td className="px-6 py-4">
                        <Link to={`/timeline/${entity.id}`} className="font-bold text-slate-800 hover:text-brand-600 transition-colors">
                          {entity.name}
                        </Link>
                        <div className="text-xs text-slate-500 font-mono font-medium mt-0.5">{entity.id}</div>
                      </td>
                      <td className="px-6 py-4 text-slate-600 font-semibold">{entity.type}</td>
                      <td className="px-6 py-4">
                        <StatusBadge 
                          band={entity.risk_band?.toLowerCase() || 'medium'} 
                        />
                      </td>
                      <td className="px-6 py-4 font-mono font-bold text-slate-600">{entity.risk_score}</td>
                      <td className="px-6 py-4 text-center">
                        <button 
                          onClick={() => toggleWatch(entity.id)}
                          className={`inline-flex items-center justify-center transition-colors ${entity.watched ? 'text-brand-600' : 'text-slate-400'}`}
                        >
                          {entity.watched ? <ToggleRight className="w-8 h-8" /> : <ToggleLeft className="w-8 h-8" />}
                        </button>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button 
                          onClick={() => openInjectModal(entity)}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand-100 text-brand-600 hover:bg-brand-200 border border-brand-200 rounded-md text-xs font-bold transition-colors shadow-sm"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm">
          <div className="glass-panel p-6 shadow-2xl w-full max-w-md">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2 drop-shadow-sm">
                <Zap className="w-5 h-5 text-brand-500" />
                Inject Demo Event
              </h3>
              <button onClick={() => setInjectModalOpen(false)} className="text-slate-400 hover:text-slate-600 bg-white/40 hover:bg-white/60 p-1.5 rounded-full transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <form onSubmit={handleInjectSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1 uppercase tracking-wider">Target Entity</label>
                <div className="text-slate-800 font-semibold glass-input px-3 py-2">
                  {selectedEntity?.name} <span className="text-slate-500 text-xs ml-2">({selectedEntity?.id})</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1 uppercase tracking-wider">Event Type</label>
                <select 
                  value={injectForm.event_type}
                  onChange={(e) => setInjectForm({ ...injectForm, event_type: e.target.value })}
                  className="w-full glass-input p-2.5 text-sm text-slate-800 font-semibold focus:border-brand-500 outline-none"
                >
                  <option value="adverse_media">Adverse Media</option>
                  <option value="transaction_anomaly">Transaction Anomaly</option>
                  <option value="sanctions_hit">Sanctions List Hit</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1 uppercase tracking-wider">Event Title</label>
                <input
                  type="text"
                  value={injectForm.title}
                  onChange={(e) => setInjectForm({ ...injectForm, title: e.target.value })}
                  className="w-full glass-input p-2.5 text-sm text-slate-800 focus:border-brand-500 outline-none"
                  placeholder="e.g. Adverse media: fraud allegation"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1 uppercase tracking-wider">Event Details</label>
                <textarea
                  value={injectForm.text}
                  onChange={(e) => setInjectForm({ ...injectForm, text: e.target.value })}
                  className="w-full glass-input p-2.5 text-sm text-slate-800 focus:border-brand-500 outline-none h-20 resize-none shadow-inner"
                  placeholder="Describe the risk event in detail..."
                  required
                />
              </div>

              <div className="pt-4 flex justify-end gap-3">
                <button 
                  type="button" 
                  onClick={() => setInjectModalOpen(false)}
                  className="px-5 py-2.5 text-sm font-bold text-slate-600 hover:text-slate-800 bg-white/60 hover:bg-white/90 border border-white/80 rounded-xl transition-all shadow-sm"
                >
                  Cancel
                </button>
                <button 
                  type="submit"
                  disabled={injectMutation.isPending}
                  className="px-5 py-2.5 text-sm font-bold bg-gradient-to-r from-brand-500 to-brand-600 hover:from-brand-600 hover:to-brand-700 text-white rounded-xl flex items-center gap-2 transition-all shadow-md disabled:opacity-50"
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

