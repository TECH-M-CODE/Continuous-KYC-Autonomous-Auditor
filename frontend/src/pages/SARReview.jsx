import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FileText, CheckCircle, XCircle, Edit3, BookOpen, MessageSquare, AlertTriangle, ChevronRight, Loader2, Save } from 'lucide-react';
import { apiClient } from '../api/client';
import { EvidenceBundle } from '../components/EvidenceBundle';
import clsx from 'clsx';

export const SARReview = () => {
  const sarId = 'sar-991'; // Hardcoded for demo, normally from useParams
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
    onSuccess: (data) => {
      if (!isEditing && !draftNarrative) {
        setDraftNarrative(data.narrative);
      }
    }
  });

  // Keep draftNarrative in sync if we aren't actively editing and new data arrives
  React.useEffect(() => {
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
      queryClient.invalidateQueries(['sar', sarId]);
      setIsEditing(false);
      addAuditEntry('SAR_EDITED', 'Version bumped to v2');
    }
  });

  const approveMutation = useMutation({
    mutationFn: (comments) => apiClient.approveSAR({ id: sarId, comments }),
    onSuccess: () => {
      queryClient.invalidateQueries(['sar', sarId]);
      addAuditEntry('SAR_APPROVED', 'Approved and filed');
      setActionNotes('');
    }
  });

  const rejectMutation = useMutation({
    mutationFn: (comments) => apiClient.rejectSAR({ id: sarId, comments }),
    onSuccess: () => {
      queryClient.invalidateQueries(['sar', sarId]);
      addAuditEntry('SAR_REJECTED', 'Rejected by officer');
      setActionNotes('');
    }
  });

  const requestInfoMutation = useMutation({
    mutationFn: (q) => apiClient.requestSARInfo({ id: sarId, question: q }),
    onSuccess: () => {
      queryClient.invalidateQueries(['sar', sarId]);
      addAuditEntry('INFO_REQUESTED', 'Investigator dispatched');
      setQuestion('');
    }
  });

  if (isLoading || !sar) {
    return <div className="flex h-full items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-brand-500" /></div>;
  }

  return (
    <div className="flex flex-col h-full space-y-6">
      {/* Degraded Draft Warning */}
      {sar.degraded_draft && (
        <div className="bg-amber-500/10 border border-amber-500/20 text-amber-400 p-4 rounded-lg flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-semibold">Degraded Mode</h4>
            <p className="text-sm opacity-90 mt-1">Draft generated in degraded mode — template + retrieved passages only. Review carefully.</p>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100 flex items-center gap-2">
            <FileText className="w-6 h-6 text-brand-400" />
            SAR Review
          </h1>
          <div className="text-sm text-slate-400 mt-1 flex items-center gap-3">
            <span>Draft ID: {sar.id}</span>
            <span>•</span>
            <span className="text-slate-300">Alert: {sar.alert_id}</span>
            <span>•</span>
            <span className="bg-slate-800 text-brand-400 px-2 py-0.5 rounded text-xs font-mono">v{sar.version}</span>
            {sar.status === 'DRAFT' || sar.status === 'PENDING_APPROVAL' ? (
              <span className="bg-amber-500/20 text-amber-400 px-2 py-0.5 rounded text-xs">Pending Review</span>
            ) : (
              <span className="bg-slate-800 text-slate-300 px-2 py-0.5 rounded text-xs uppercase">{sar.status}</span>
            )}
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          {isEditing ? (
            <>
              <button 
                className="px-4 py-2 bg-slate-800 text-slate-300 hover:text-slate-100 rounded-lg text-sm font-medium transition-colors"
                onClick={() => { setIsEditing(false); setDraftNarrative(sar.narrative); }}
              >
                Cancel
              </button>
              <button 
                className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white hover:bg-brand-500 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                onClick={() => editMutation.mutate(draftNarrative)}
                disabled={editMutation.isPending}
              >
                {editMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                Save Changes
              </button>
            </>
          ) : (
            <button 
              className="flex items-center gap-2 px-4 py-2 bg-slate-800 text-slate-300 hover:text-slate-100 rounded-lg text-sm font-medium transition-colors"
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
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col flex-1">
            <h3 className="text-lg font-medium text-slate-200 mb-4">Generated Narrative</h3>
            {isEditing ? (
              <textarea
                className="flex-1 w-full bg-slate-950 border border-slate-700 rounded-lg p-4 text-slate-300 font-mono text-sm leading-relaxed focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none resize-none"
                value={draftNarrative}
                onChange={(e) => setDraftNarrative(e.target.value)}
              />
            ) : (
              <div className="flex-1 w-full bg-slate-950 border border-slate-800 rounded-lg p-4 text-slate-300 font-serif text-base leading-relaxed overflow-y-auto whitespace-pre-wrap">
                {sar.narrative}
              </div>
            )}
          </div>

          {/* Action Box */}
          {(sar.status === 'DRAFT' || sar.status === 'PENDING_APPROVAL') && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <h3 className="text-sm font-medium text-slate-200 mb-4">Decision Actions</h3>
              
              <div className="space-y-4">
                <textarea
                  placeholder="Review notes (required for approve/reject)..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-sm text-slate-300 h-20 resize-none focus:border-brand-500 outline-none"
                  value={actionNotes}
                  onChange={(e) => setActionNotes(e.target.value)}
                />
                <div className="flex gap-3">
                  <button 
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-red-500/10 text-red-400 hover:bg-red-500/20 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                    onClick={() => rejectMutation.mutate(actionNotes)}
                    disabled={!actionNotes || rejectMutation.isPending}
                  >
                    {rejectMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
                    Reject Draft
                  </button>
                  <button 
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-brand-600 text-white hover:bg-brand-500 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                    onClick={() => approveMutation.mutate(actionNotes)}
                    disabled={!actionNotes || approveMutation.isPending}
                  >
                    {approveMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                    Approve & File
                  </button>
                </div>

                <div className="pt-4 border-t border-slate-800">
                  <div className="flex gap-3">
                    <input
                      type="text"
                      placeholder="Ask the Investigator a question..."
                      className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-300 focus:border-brand-500 outline-none"
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                    />
                    <button 
                      className="flex items-center gap-2 px-4 py-2 bg-slate-800 text-slate-300 hover:text-slate-100 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
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

        {/* Right Pane: Evidence & Citations */}
        <div className="w-1/3 flex flex-col gap-6 overflow-y-auto">
          {/* Mini Audit Feed */}
          {optimisticAudit.length > 0 && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-3">Session Activity</h3>
              <div className="space-y-3">
                {optimisticAudit.map((entry, idx) => (
                  <div key={idx} className="flex gap-3 text-sm">
                    <div className="text-slate-500 shrink-0 mt-0.5">{entry.time}</div>
                    <div>
                      <div className="text-brand-400 font-medium">{entry.actor} <span className="text-slate-400 font-normal">{entry.action}</span></div>
                      <div className="text-slate-300 text-xs mt-0.5">{entry.detail}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Regulatory Basis (Chips) */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-brand-400" />
              Regulatory Citations
            </h3>
            <div className="flex flex-wrap gap-2">
              {sar.citations?.map((cit, idx) => (
                <button
                  key={idx}
                  onClick={() => setSelectedCitation(selectedCitation === cit ? null : cit)}
                  className={clsx(
                    "px-3 py-1.5 rounded-full text-xs font-medium transition-colors border flex items-center gap-1",
                    selectedCitation === cit 
                      ? "bg-brand-500/20 border-brand-500/50 text-brand-400"
                      : "bg-slate-800 border-slate-700 text-slate-300 hover:border-slate-600"
                  )}
                >
                  {cit.source}
                </button>
              ))}
            </div>

            {/* Citation Drawer / Inline Expansion */}
            {selectedCitation && (
              <div className="mt-4 p-4 bg-slate-950 border border-brand-500/30 rounded-lg animate-in fade-in slide-in-from-top-2">
              <div className="text-xs font-bold text-brand-400 mb-1">{selectedCitation.source}</div>
                <p className="text-sm text-slate-300 italic leading-relaxed">"{selectedCitation.context}"</p>
              </div>
            )}
          </div>

          {/* Evidence Bundle — uses citations as the evidence source */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Compiled Evidence</h3>
            <EvidenceBundle evidence={sar.citations?.map(c => ({ source: c.source, snippet: c.context, relevance: 'Medium' })) || []} />
          </div>
        </div>
      </div>
    </div>
  );
};

