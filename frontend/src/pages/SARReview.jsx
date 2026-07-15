import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FileText, CheckCircle, XCircle, Edit3, BookOpen, MessageSquare, AlertTriangle, ArrowLeft, Loader2, Save, Download, Clock, ChevronRight } from 'lucide-react';
import { apiClient } from '../api/client';
import { EvidenceBundle } from '../components/EvidenceBundle';
import clsx from 'clsx';

// ==========================================
// CSV Export Helper
// ==========================================
const downloadCSV = (sars) => {
  if (!sars || !sars.length) return;
  const headers = ['SAR ID', 'Alert ID', 'Entity Name', 'Status', 'Date', 'Version'];
  const rows = sars.map(s => [
    s.id, s.alert_id, s.entity_name, s.status, new Date(s.created_at).toLocaleString(), s.version
  ]);
  
  let csvContent = "data:text/csv;charset=utf-8,";
  csvContent += headers.join(",") + "\n";
  rows.forEach(row => {
    // Escape quotes and wrap in quotes
    const cleanRow = row.map(v => `"${String(v).replace(/"/g, '""')}"`);
    csvContent += cleanRow.join(",") + "\n";
  });
  
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", `SAR_Logs_${new Date().toISOString().split('T')[0]}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

// ==========================================
// SAR Detail View Component
// ==========================================
const SARDetailView = ({ sarId }) => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  
  const [isEditing, setIsEditing] = useState(false);
  const [draftNarrative, setDraftNarrative] = useState('');
  const [actionNotes, setActionNotes] = useState('');
  const [question, setQuestion] = useState('');
  const [selectedCitation, setSelectedCitation] = useState(null);
  const [optimisticAudit, setOptimisticAudit] = useState([]);

  const { data: sar, isLoading } = useQuery({
    queryKey: ['sar', sarId],
    queryFn: () => apiClient.getSAR(sarId),
    enabled: !!sarId,
    onSuccess: (data) => {
      if (!isEditing && !draftNarrative) {
        setDraftNarrative(data.narrative);
      }
    }
  });

  useEffect(() => {
    if (sar && !isEditing) {
      setDraftNarrative(sar.narrative);
    }
  }, [sar, isEditing]);

  const addAuditEntry = (action, detail) => {
    setOptimisticAudit(prev => [{
      time: new Date().toLocaleTimeString(),
      actor: 'Human Officer',
      action,
      detail
    }, ...prev]);
  };

  const editMutation = useMutation({
    mutationFn: (narrative) => apiClient.editSAR({ id: sarId, narrative }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sar', sarId] });
      setIsEditing(false);
      addAuditEntry('SAR_EDITED', 'Version bumped to v2');
    }
  });

  const approveMutation = useMutation({
    mutationFn: (comments) => apiClient.approveSAR({ id: sarId, comments }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sar', sarId] });
      queryClient.invalidateQueries({ queryKey: ['sars'] });
      navigate('/sar');
    }
  });

  const rejectMutation = useMutation({
    mutationFn: (comments) => apiClient.rejectSAR({ id: sarId, comments }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sar', sarId] });
      queryClient.invalidateQueries({ queryKey: ['sars'] });
      navigate('/sar');
    }
  });

  const requestInfoMutation = useMutation({
    mutationFn: (q) => apiClient.requestSARInfo({ id: sarId, question: q }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sar', sarId] });
      addAuditEntry('INFO_REQUESTED', 'Investigator dispatched');
      setQuestion('');
    }
  });

  if (isLoading) {
    return <div className="flex h-full items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-brand-500" /></div>;
  }
  if (!sar) return null;

  return (
    <div className="flex flex-col h-full space-y-6">
      <div className="flex items-center gap-4">
        <button 
          onClick={() => navigate('/sar')}
          className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <FileText className="w-6 h-6 text-brand-500" />
            SAR Review
          </h1>
          <div className="text-sm text-slate-500 mt-1 flex items-center gap-3 font-medium">
            <span>Draft ID: {sar.id}</span>
            <span>•</span>
            <span className="text-slate-600">Alert: {sar.alert_id}</span>
            <span>•</span>
            <span className="bg-white/60 text-brand-600 px-2 py-0.5 rounded text-xs font-mono shadow-sm">v{sar.version}</span>
            {sar.status === 'DRAFT' || sar.status === 'PENDING_APPROVAL' ? (
              <span className="bg-amber-100 text-amber-600 px-2 py-0.5 rounded text-xs border border-amber-200">Pending Review</span>
            ) : (
              <span className="bg-white/60 text-slate-600 px-2 py-0.5 rounded text-xs uppercase border border-slate-200">{sar.status}</span>
            )}
          </div>
        </div>
        
        <div className="ml-auto flex items-center gap-3">
          {isEditing ? (
            <>
              <button 
                className="px-5 py-2.5 bg-white/60 text-slate-600 hover:text-slate-800 hover:bg-white/90 border border-white/80 rounded-xl text-sm font-semibold transition-all shadow-sm"
                onClick={() => { setIsEditing(false); setDraftNarrative(sar.narrative); }}
              >
                Cancel
              </button>
              <button 
                className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-brand-500 to-brand-600 text-white hover:from-brand-600 hover:to-brand-700 rounded-xl text-sm font-bold transition-all shadow-lg shadow-brand-500/30 disabled:opacity-50"
                onClick={() => editMutation.mutate(draftNarrative)}
                disabled={editMutation.isPending}
              >
                {editMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                Save Changes
              </button>
            </>
          ) : (
            <button 
              className="flex items-center gap-2 px-5 py-2.5 bg-white/60 text-slate-600 hover:text-slate-800 hover:bg-white/90 border border-white/80 rounded-xl text-sm font-semibold transition-all shadow-sm"
              onClick={() => setIsEditing(true)}
              disabled={sar.status !== 'DRAFT' && sar.status !== 'PENDING_APPROVAL'}
            >
              <Edit3 className="w-4 h-4" />
              Edit Narrative
            </button>
          )}
        </div>
      </div>

      <div className="flex flex-1 gap-6 min-h-[500px]">
        {/* Left Pane: Narrative & Actions */}
        <div className="w-2/3 flex flex-col gap-6">
          <div className="glass-panel p-6 flex flex-col flex-1">
            <h3 className="text-lg font-bold text-slate-800 mb-4">Generated Narrative</h3>
            {isEditing ? (
              <textarea
                className="flex-1 w-full bg-white/60 border border-white/80 rounded-xl p-5 text-slate-800 font-mono text-sm leading-relaxed focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none resize-none shadow-inner"
                value={draftNarrative}
                onChange={(e) => setDraftNarrative(e.target.value)}
              />
            ) : (
              <div className="flex-1 w-full bg-white/40 border border-white/60 rounded-xl p-5 text-slate-700 font-serif text-base leading-relaxed overflow-y-auto whitespace-pre-wrap shadow-inner">
                {sar.narrative}
              </div>
            )}
          </div>

          {(sar.status === 'DRAFT' || sar.status === 'PENDING_APPROVAL') && (
            <div className="glass-panel p-6">
              <h3 className="text-sm font-bold text-slate-800 mb-4">Decision Actions</h3>
              
              <div className="space-y-4">
                <textarea
                  placeholder="Review notes (required for approve/reject)..."
                  className="w-full bg-white/50 border border-white/60 rounded-xl p-4 text-sm text-slate-800 h-20 resize-none focus:border-brand-500 outline-none shadow-inner"
                  value={actionNotes}
                  onChange={(e) => setActionNotes(e.target.value)}
                />
                <div className="flex gap-4">
                  <button 
                    className="flex-1 flex items-center justify-center gap-2 px-5 py-2.5 bg-red-100 text-red-600 hover:bg-red-200 border border-red-200 rounded-xl text-sm font-bold transition-all shadow-sm disabled:opacity-50"
                    onClick={() => rejectMutation.mutate(actionNotes)}
                    disabled={!actionNotes || rejectMutation.isPending}
                  >
                    {rejectMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
                    Reject Draft
                  </button>
                  <button 
                    className="flex-1 flex items-center justify-center gap-2 px-5 py-2.5 bg-gradient-to-r from-emerald-500 to-emerald-600 text-white hover:from-emerald-600 hover:to-emerald-700 rounded-xl text-sm font-bold transition-all shadow-md disabled:opacity-50"
                    onClick={() => approveMutation.mutate(actionNotes)}
                    disabled={!actionNotes || approveMutation.isPending}
                  >
                    {approveMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                    Approve & File
                  </button>
                </div>

                <div className="pt-4 border-t border-white/50">
                  <div className="flex gap-3">
                    <input
                      type="text"
                      placeholder="Ask the Investigator a question..."
                      className="flex-1 glass-input px-4 py-2 text-sm text-slate-800"
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                    />
                    <button 
                      className="flex items-center gap-2 px-5 py-2 bg-white/60 text-brand-600 hover:text-brand-700 hover:bg-white/90 border border-white/80 rounded-xl text-sm font-bold transition-all shadow-sm disabled:opacity-50"
                      onClick={() => requestInfoMutation.mutate(question)}
                      disabled={!question || requestInfoMutation.isPending}
                    >
                      {requestInfoMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <MessageSquare className="w-4 h-4" />}
                      Request Info
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Pane */}
        <div className="w-1/3 flex flex-col gap-6 overflow-y-auto pr-2">
          {optimisticAudit.length > 0 && (
            <div className="glass-panel p-5">
              <h3 className="text-sm font-bold text-slate-800 mb-3">Session Activity</h3>
              <div className="space-y-3">
                {optimisticAudit.map((entry, idx) => (
                  <div key={idx} className="flex gap-3 text-sm">
                    <div className="text-slate-500 shrink-0 mt-0.5">{entry.time}</div>
                    <div>
                      <div className="text-brand-600 font-bold">{entry.actor} <span className="text-slate-600 font-medium">{entry.action}</span></div>
                      <div className="text-slate-500 text-xs mt-0.5">{entry.detail}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="glass-panel p-5">
            <h3 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-brand-500" />
              Regulatory Citations
            </h3>
            <div className="flex flex-wrap gap-2">
              {sar.citations?.map((cit, idx) => (
                <button
                  key={idx}
                  onClick={() => setSelectedCitation(selectedCitation === cit ? null : cit)}
                  className={clsx(
                    "px-3 py-1.5 rounded-full text-xs font-bold transition-all border flex items-center gap-1 shadow-sm",
                    selectedCitation === cit 
                      ? "bg-brand-500 text-white border-brand-500 shadow-brand-500/30"
                      : "bg-white/60 border-white/80 text-slate-600 hover:bg-white/80"
                  )}
                >
                  {cit.source}
                </button>
              ))}
            </div>

            {selectedCitation && (
              <div className="mt-4 p-4 bg-white/50 border border-white/60 rounded-xl animate-in fade-in slide-in-from-top-2 shadow-inner">
              <div className="text-xs font-bold text-brand-600 mb-1">{selectedCitation.source}</div>
                <p className="text-sm text-slate-700 italic leading-relaxed">"{selectedCitation.context}"</p>
              </div>
            )}
          </div>

          <div className="glass-panel p-5">
            <h3 className="text-sm font-bold text-slate-800 mb-4">Compiled Evidence</h3>
            <EvidenceBundle evidence={sar.citations?.map(c => ({ source: c.source, snippet: c.context, relevance: 'Medium' })) || []} />
          </div>
        </div>
      </div>
    </div>
  );
};

// ==========================================
// Main SAR Review Page (List View Wrapper)
// ==========================================
export const SARReview = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('PENDING'); // PENDING or LOGS
  const [dateFilter, setDateFilter] = useState('ALL'); // ALL, TODAY, YESTERDAY, LAST_WEEK, LAST_MONTH, LAST_YEAR
  
  const { data: sars = [], isLoading } = useQuery({
    queryKey: ['sars', { limit: 1000 }],
    queryFn: () => apiClient.getSARs({ limit: 1000 })
  });

  // Derived filtered data
  const pendingSars = useMemo(() => sars.filter(s => s.status === 'DRAFT' || s.status === 'PENDING_APPROVAL'), [sars]);
  
  const logSars = useMemo(() => {
    let filtered = sars.filter(s => s.status === 'APPROVED' || s.status === 'REJECTED');
    if (dateFilter === 'ALL') return filtered;
    
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    
    return filtered.filter(sar => {
      const d = new Date(sar.created_at);
      switch(dateFilter) {
        case 'TODAY': return d >= todayStart;
        case 'YESTERDAY': {
          const yest = new Date(todayStart); yest.setDate(yest.getDate() - 1);
          return d >= yest && d < todayStart;
        }
        case 'LAST_WEEK': {
          const lw = new Date(todayStart); lw.setDate(lw.getDate() - 7);
          return d >= lw;
        }
        case 'LAST_MONTH': {
          const lm = new Date(todayStart); lm.setMonth(lm.getMonth() - 1);
          return d >= lm;
        }
        case 'LAST_YEAR': {
          const ly = new Date(todayStart); ly.setFullYear(ly.getFullYear() - 1);
          return d >= ly;
        }
        default: return true;
      }
    });
  }, [sars, dateFilter]);

  if (id) {
    return <SARDetailView sarId={id} />;
  }

  return (
    <div className="flex flex-col h-full space-y-6 max-w-7xl mx-auto w-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <FileText className="w-6 h-6 text-brand-500" />
            SAR Reports
          </h1>
          <p className="text-sm text-slate-500 mt-1 font-medium">Review pending drafts or access approved/rejected history logs.</p>
        </div>
      </div>

      <div className="flex gap-4 border-b border-white/50 pb-2">
        <button
          onClick={() => setActiveTab('PENDING')}
          className={clsx(
            "px-4 py-2 font-bold text-sm transition-all rounded-lg",
            activeTab === 'PENDING' ? "bg-white text-brand-600 shadow-sm border border-white/80" : "text-slate-500 hover:text-slate-800 hover:bg-white/40"
          )}
        >
          Pending Review ({pendingSars.length})
        </button>
        <button
          onClick={() => setActiveTab('LOGS')}
          className={clsx(
            "px-4 py-2 font-bold text-sm transition-all rounded-lg flex items-center gap-2",
            activeTab === 'LOGS' ? "bg-white text-brand-600 shadow-sm border border-white/80" : "text-slate-500 hover:text-slate-800 hover:bg-white/40"
          )}
        >
          <Clock className="w-4 h-4" />
          SAR Logs
        </button>
      </div>

      {isLoading ? (
        <div className="flex py-20 items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-brand-500" /></div>
      ) : activeTab === 'PENDING' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {pendingSars.length === 0 ? (
            <div className="col-span-full py-16 text-center text-slate-500 font-semibold glass-panel">
              No SARs currently pending review.
            </div>
          ) : (
            pendingSars.map(sar => (
              <div 
                key={sar.id} 
                className="glass-panel p-6 cursor-pointer glass-panel-hover"
                onClick={() => navigate(`/sar/${sar.id}`)}
              >
                <div className="flex justify-between items-start mb-4">
                  <div className="px-3 py-1 bg-amber-100 text-amber-600 text-xs font-bold rounded-md shadow-inner border border-amber-200">Pending</div>
                  <div className="text-xs font-semibold text-slate-500">{new Date(sar.created_at).toLocaleDateString()}</div>
                </div>
                <h3 className="text-lg font-bold text-slate-800 mb-1">{sar.entity_name || 'Unknown Entity'}</h3>
                <p className="text-sm text-slate-500 mb-4 font-mono font-medium">Draft ID: {sar.id.split('-')[0]}...</p>
                
                <div className="flex items-center text-brand-600 text-sm font-bold group">
                  Review Report
                  <ChevronRight className="w-4 h-4 ml-1 transition-transform group-hover:translate-x-1" />
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          <div className="flex items-center justify-between glass-panel p-4">
            <div className="flex items-center gap-3">
              <label className="text-sm font-bold text-slate-700">Filter Date:</label>
              <select 
                className="glass-input text-slate-800 font-semibold text-sm rounded-lg px-3 py-1.5 focus:ring-brand-500"
                value={dateFilter}
                onChange={(e) => setDateFilter(e.target.value)}
              >
                <option value="ALL">All Time</option>
                <option value="TODAY">Today</option>
                <option value="YESTERDAY">Yesterday</option>
                <option value="LAST_WEEK">Last Week</option>
                <option value="LAST_MONTH">Last Month</option>
                <option value="LAST_YEAR">Last Year</option>
              </select>
            </div>
            <button
              onClick={() => downloadCSV(logSars)}
              disabled={logSars.length === 0}
              className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 disabled:opacity-50 text-white text-sm font-bold rounded-xl transition-all shadow-md hover:shadow-lg"
            >
              <Download className="w-4 h-4" />
              Export Excel (CSV)
            </button>
          </div>

          <div className="glass-panel overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-600">
                <thead className="bg-white/40 text-slate-700 uppercase font-bold text-xs border-b border-white/50 backdrop-blur-sm">
                  <tr>
                    <th className="px-6 py-4">Status</th>
                    <th className="px-6 py-4">Entity</th>
                    <th className="px-6 py-4">Draft ID</th>
                    <th className="px-6 py-4">Date</th>
                    <th className="px-6 py-4">Version</th>
                    <th className="px-6 py-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/40">
                  {logSars.length === 0 ? (
                    <tr>
                      <td colSpan="6" className="px-6 py-8 text-center text-slate-500 font-medium">
                        No logs found for this date range.
                      </td>
                    </tr>
                  ) : (
                    logSars.map(sar => (
                      <tr key={sar.id} className="hover:bg-white/40 transition-colors">
                        <td className="px-6 py-4">
                          <span className={clsx(
                            "px-3 py-1.5 text-xs font-bold rounded-md flex items-center gap-1.5 w-max border shadow-sm",
                            sar.status === 'APPROVED' ? "bg-emerald-100 text-emerald-600 border-emerald-200" : "bg-red-100 text-red-600 border-red-200"
                          )}>
                            {sar.status === 'APPROVED' ? <CheckCircle className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                            {sar.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 font-bold text-slate-800">{sar.entity_name}</td>
                        <td className="px-6 py-4 font-mono font-medium">{sar.id.substring(0, 8)}...</td>
                        <td className="px-6 py-4 font-medium">{new Date(sar.created_at).toLocaleString()}</td>
                        <td className="px-6 py-4 font-medium">v{sar.version}</td>
                        <td className="px-6 py-4 text-right">
                          <button 
                            onClick={() => navigate(`/sar/${sar.id}`)}
                            className="text-brand-600 hover:text-brand-700 font-bold"
                          >
                            View
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
