import React, { useState, useMemo } from 'react';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ShieldAlert, Zap, Search, ToggleLeft, ToggleRight, Loader2, X, TrendingUp, AlertTriangle, ShieldCheck } from 'lucide-react';
import { StatusBadge } from '../components/StatusBadge';
import { DetectionHealth } from '../components/DetectionHealth';
import { PipelineProgress } from '../components/PipelineProgress';
import { apiClient } from '../api/client';
import clsx from 'clsx';

const BAND_BAR = {
  CRITICAL: '#ef4444',
  HIGH:     '#f97316',
  MEDIUM:   '#eab308',
  LOW:      '#22c55e',
};

const EVENT_TYPES = [
  { value: 'adverse_media',      label: 'Adverse Media' },
  { value: 'transaction_anomaly', label: 'Transaction Anomaly' },
  { value: 'sanctions_hit',      label: 'Sanctions List Hit' },
];

export const AdminWatchlist = () => {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [injectModalOpen, setInjectModalOpen] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState(null);
  const [injectForm, setInjectForm] = useState({ eventTypes: ['adverse_media'], title: '', text: '' });
  const [isInjecting, setIsInjecting] = useState(false);
  const [progress, setProgress] = useState({ open: false, count: 1, name: '' });

  // Add Customer States
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState({ name: '', jurisdiction: '', sector: '', type: 'COMPANY' });
  const [duplicateMatches, setDuplicateMatches] = useState([]);
  const [showDuplicateModal, setShowDuplicateModal] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [verificationResult, setVerificationResult] = useState(null);

  const addCustomerMutation = useMutation({
    mutationFn: apiClient.addCustomer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] });
      setIsModalOpen(false);
      setFormData({ name: '', jurisdiction: '', sector: '', type: 'COMPANY' });
    },
  });

  const { data: entities = [], isLoading } = useQuery({
    queryKey: ['watchlist'],
    queryFn: () => apiClient.getWatchlist({ limit: 100 }),
  });

  const openInjectModal = (entity) => {
    setSelectedEntity(entity);
    setInjectForm({
      eventTypes: ['adverse_media'],
      title: `Risk signal detected for ${entity.name}`,
      text: `Automated system flagged ${entity.name} for compliance review.`,
    });
    setInjectModalOpen(true);
  };

  const toggleType = (value) => {
    setInjectForm(f => ({
      ...f,
      eventTypes: f.eventTypes.includes(value)
        ? f.eventTypes.filter(t => t !== value)
        : [...f.eventTypes, value],
    }));
  };

  const handleInjectSubmit = async (e) => {
    e.preventDefault();
    const types = injectForm.eventTypes;
    if (types.length === 0 || !selectedEntity) return;
    setIsInjecting(true);
    try {
      // One event per selected type — lets the analyst simulate several
      // concurrent typologies for the same entity in a single action.
      for (const t of types) {
        await apiClient.injectEvent({
          event_type: t,
          title: injectForm.title,
          text: injectForm.text,
          entity_hint: selectedEntity.name,
        });
      }
    } finally {
      setIsInjecting(false);
      setInjectModalOpen(false);
      setProgress({ open: true, count: types.length, name: selectedEntity.name });
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-alerts'] });
    }
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
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <ShieldAlert className="w-6 h-6 text-brand-400" />
            Entities & Watchlist
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">Monitor entities, onboard customers, and inject synthetic events.</p>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={() => setIsModalOpen(true)}
            className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white font-medium rounded-lg transition-colors shadow-lg cursor-pointer"
          >
            Onboard Customer
          </button>
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
                <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">
                  Event Type(s) — select one or more
                </label>
                <div className="space-y-1.5">
                  {EVENT_TYPES.map(t => {
                    const checked = injectForm.eventTypes.includes(t.value);
                    return (
                      <label
                        key={t.value}
                        className={clsx(
                          'flex items-center gap-2.5 px-3 py-2 rounded-xl border cursor-pointer transition-all',
                          checked
                            ? 'bg-brand-500/10 border-brand-500/40 text-brand-200'
                            : 'bg-slate-800/60 border-slate-700 text-slate-400 hover:border-slate-600'
                        )}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleType(t.value)}
                          className="accent-brand-500 w-4 h-4"
                        />
                        <span className="text-sm font-medium">{t.label}</span>
                      </label>
                    );
                  })}
                </div>
                {injectForm.eventTypes.length === 0 && (
                  <p className="text-[11px] text-amber-400 mt-1.5">Select at least one event type.</p>
                )}
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
                <button type="submit" disabled={isInjecting || injectForm.eventTypes.length === 0}
                  className="flex items-center gap-2 px-5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-sm font-semibold transition-colors disabled:opacity-50">
                  {isInjecting
                    ? <><Loader2 className="w-4 h-4 animate-spin" /> Injecting…</>
                    : <><Zap className="w-4 h-4" /> Inject {injectForm.eventTypes.length > 1 ? `${injectForm.eventTypes.length} Events` : 'Event'}</>}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Live pipeline progress overlay ── */}
      <PipelineProgress
        open={progress.open}
        expectedCount={progress.count}
        entityName={progress.name}
        onClose={() => setProgress(p => ({ ...p, open: false }))}
      />

      {/* Verification Result Popup */}
      {verificationResult && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-[70]" onClick={() => setVerificationResult(null)}>
          <div className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-sm p-8 shadow-2xl text-center transform scale-100 transition-transform">
            {verificationResult.status === 'SAFE' ? (
              <div className="mx-auto w-20 h-20 bg-emerald-500/20 rounded-full flex items-center justify-center mb-6">
                <ShieldCheck className="w-10 h-10 text-emerald-400" />
              </div>
            ) : (
              <div className="mx-auto w-20 h-20 bg-red-500/20 rounded-full flex items-center justify-center mb-6">
                <ShieldAlert className="w-10 h-10 text-red-400" />
              </div>
            )}
            
            <h2 className={`text-2xl font-bold mb-2 ${verificationResult.status === 'SAFE' ? 'text-emerald-400' : 'text-red-400'}`}>
              {verificationResult.status === 'SAFE' ? 'Customer is Safe' : 'Customer At Risk'}
            </h2>
            
            <p className="text-slate-300 mb-8">
              Existing risk profile is <strong className="text-slate-100">{verificationResult.band}</strong>. No new profile was created.
            </p>
            
            <button
              onClick={() => setVerificationResult(null)}
              className="w-full py-3 bg-slate-800 hover:bg-slate-700 text-white font-medium rounded-lg transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* Duplicate Check Modal */}
      {showDuplicateModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-[60]">
          <div className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-lg p-6 shadow-2xl">
            <div className="flex items-center gap-3 mb-4 text-orange-400">
              <AlertTriangle className="w-6 h-6" />
              <h2 className="text-xl font-bold">Potential Duplicate Detected</h2>
            </div>
            <p className="text-slate-300 mb-6">
              We found existing records matching this name. Is this the same person/entity?
            </p>
            
            <div className="space-y-3 mb-6 max-h-60 overflow-y-auto">
              {duplicateMatches.map(match => (
                <div key={match.id} className="bg-slate-800 p-4 rounded-lg border border-slate-700 flex justify-between items-center">
                  <div>
                    <p className="font-semibold text-slate-100">{match.name}</p>
                    <p className="text-sm text-slate-400">{match.role || match.type}</p>
                  </div>
                  <button
                    onClick={() => {
                      const isSafe = ['LOW', 'MEDIUM'].includes(match.risk_band);
                      setVerificationResult({ status: isSafe ? 'SAFE' : 'AT_RISK', band: match.risk_band });
                      setShowDuplicateModal(false);
                      setIsModalOpen(false);
                    }}
                    className="px-3 py-1.5 bg-brand-600 hover:bg-brand-500 text-white text-sm font-medium rounded-md transition-colors"
                  >
                    Yes, this is them
                  </button>
                </div>
              ))}
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-slate-800">
              <button
                onClick={() => setShowDuplicateModal(false)}
                className="px-4 py-2 text-slate-300 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  const finalName = formData.type === 'PERSON' 
                    ? `${formData.firstName || ''} ${formData.lastName || ''}`.trim() 
                    : formData.name;
                  setShowDuplicateModal(false);
                  addCustomerMutation.mutate({ ...formData, name: finalName });
                }}
                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white font-medium rounded-lg transition-colors"
              >
                No, create new customer
              </button>
            </div>
          </div>
        </div>
      )}

      {isModalOpen && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 animate-fade-in">
          <div className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-md p-6 shadow-2xl animate-slide-up">
            <h2 className="text-xl font-bold text-slate-100 mb-4">Onboard Customer</h2>
            
            <div className="flex gap-4 mb-6">
              <label className="flex items-center gap-2 text-slate-300">
                <input 
                  type="radio" 
                  name="customerType" 
                  checked={formData.type === 'PERSON'} 
                  onChange={() => setFormData({ ...formData, type: 'PERSON', name: '', firstName: '', lastName: '' })}
                  className="text-brand-500 focus:ring-brand-500 bg-slate-800 border-slate-600"
                />
                Person
              </label>
              <label className="flex items-center gap-2 text-slate-300">
                <input 
                  type="radio" 
                  name="customerType" 
                  checked={formData.type !== 'PERSON'} 
                  onChange={() => setFormData({ ...formData, type: 'COMPANY', name: '', firstName: '', lastName: '' })}
                  className="text-brand-500 focus:ring-brand-500 bg-slate-800 border-slate-600"
                />
                Company
              </label>
            </div>

            <div className="space-y-4">
              {formData.type === 'PERSON' ? (
                <>
                  <div className="flex gap-4">
                    <div className="flex-1">
                      <label className="block text-sm font-medium text-slate-400 mb-1">First Name</label>
                      <input
                        type="text"
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-brand-500"
                        value={formData.firstName || ''}
                        onChange={(e) => setFormData({ ...formData, firstName: e.target.value })}
                        placeholder="e.g. Khushi"
                      />
                    </div>
                    <div className="flex-1">
                      <label className="block text-sm font-medium text-slate-400 mb-1">Last Name</label>
                      <input
                        type="text"
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-brand-500"
                        value={formData.lastName || ''}
                        onChange={(e) => setFormData({ ...formData, lastName: e.target.value })}
                        placeholder="e.g. Katiyar"
                      />
                    </div>
                  </div>
                </>
              ) : (
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-1">Company Name</label>
                  <input
                    type="text"
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-brand-500"
                    value={formData.name || ''}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="e.g. Acme Corp"
                  />
                </div>
              )}
              
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1">Jurisdiction / Country</label>
                <input
                  type="text"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-brand-500 transition-colors"
                  value={formData.jurisdiction}
                  onChange={(e) => setFormData({ ...formData, jurisdiction: e.target.value })}
                  placeholder="e.g. US, UK, India"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1">Sector / Industry</label>
                <input
                  type="text"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-brand-500 transition-colors"
                  value={formData.sector}
                  onChange={(e) => setFormData({ ...formData, sector: e.target.value })}
                  placeholder="e.g. Finance, Technology"
                />
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setIsModalOpen(false)}
                className="px-4 py-2 text-slate-300 hover:text-white transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  const finalName = formData.type === 'PERSON' 
                    ? `${formData.firstName || ''} ${formData.lastName || ''}`.trim() 
                    : formData.name;
                  
                  setIsChecking(true);
                  try {
                    const matches = await apiClient.checkDuplicate(finalName);
                    if (matches && matches.length > 0) {
                      setDuplicateMatches(matches);
                      setShowDuplicateModal(true);
                    } else {
                      addCustomerMutation.mutate({ ...formData, name: finalName });
                    }
                  } catch(e) {
                    addCustomerMutation.mutate({ ...formData, name: finalName });
                  } finally {
                    setIsChecking(false);
                  }
                }}
                disabled={addCustomerMutation.isPending || isChecking || (formData.type === 'PERSON' ? (!formData.firstName && !formData.lastName) : !formData.name)}
                className="px-4 py-2 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white font-medium rounded-lg transition-colors cursor-pointer"
              >
                {addCustomerMutation.isPending || isChecking ? 'Adding...' : 'Onboard Customer'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
