import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  FileText, CheckCircle, XCircle, Edit3, BookOpen,
  MessageSquare, AlertTriangle, Loader2, Save, ChevronRight,
  Clock, Check
} from 'lucide-react';
import { apiClient } from '../api/client';
import { EvidenceBundle } from '../components/EvidenceBundle';
import clsx from 'clsx';

const STATUS_STEPS = ['DRAFT', 'PENDING_APPROVAL', 'APPROVED'];

function StatusStepper({ current }) {
  const step = STATUS_STEPS.indexOf(current);
  return (
    <div className="flex items-center gap-0">
      {STATUS_STEPS.map((s, i) => (
        <React.Fragment key={s}>
          <div className="flex items-center gap-1.5">
            <div className={clsx(
              'w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border transition-all',
              i < step  ? 'bg-emerald-500 border-emerald-500 text-white' :
              i === step ? 'bg-brand-500 border-brand-500 text-white shadow-[0_0_10px_rgba(10,126,255,0.5)]' :
                           'bg-slate-800 border-slate-700 text-slate-500'
            )}>
              {i < step ? <Check className="w-3 h-3" /> : i + 1}
            </div>
            <span className={clsx(
              'text-xs font-medium hidden sm:block',
              i === step ? 'text-brand-300' : i < step ? 'text-emerald-400' : 'text-slate-600'
            )}>
              {s.replace('_', ' ')}
            </span>
          </div>
          {i < STATUS_STEPS.length - 1 && (
            <div className={clsx('w-8 h-px mx-1', i < step ? 'bg-emerald-500/50' : 'bg-slate-800')} />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

export const SARReview = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [isEditing, setIsEditing]         = useState(false);
  const [draftNarrative, setDraftNarrative] = useState('');
  const [actionNotes, setActionNotes]     = useState('');
  const [question, setQuestion]           = useState('');
  const [selectedCitation, setSelectedCitation] = useState(null);
  const [optimisticAudit, setOptimisticAudit]   = useState([]);

  // SAR list for sidebar
  const { data: allSars = [] } = useQuery({
    queryKey: ['sars', 'all'],
    queryFn: () => apiClient.getSARs({ limit: 50 }),
  });

  // Latest redirect
  const { data: latestSars = [], isLoading: isLatestLoading } = useQuery({
    queryKey: ['sars', 'latest'],
    queryFn: () => apiClient.getSARs({ limit: 1 }),
    enabled: !id,
  });

  useEffect(() => {
    if (!id && latestSars.length > 0)
      navigate(`/sar/${latestSars[0].id}`, { replace: true });
  }, [id, latestSars, navigate]);

  const { data: sar, isLoading } = useQuery({
    queryKey: ['sar', id],
    queryFn: () => apiClient.getSAR(id),
    enabled: !!id,
  });

  useEffect(() => {
    if (sar && !isEditing) setDraftNarrative(sar.narrative || '');
  }, [sar, isEditing]);

  const addAuditEntry = (action, detail) =>
    setOptimisticAudit(prev => [{ time: new Date().toLocaleTimeString(), actor: 'Human Officer', action, detail }, ...prev]);

  const editMutation = useMutation({
    mutationFn: (narrative) => apiClient.editSAR({ id, narrative }),
    onSuccess: () => { queryClient.invalidateQueries(['sar', id]); setIsEditing(false); addAuditEntry('SAR_EDITED', 'Narrative updated'); },
  });
  const approveMutation = useMutation({
    mutationFn: (comments) => apiClient.approveSAR({ id, comments }),
    onSuccess: () => { queryClient.invalidateQueries(['sar', id]); addAuditEntry('SAR_APPROVED', 'Filed to regulatory'); setActionNotes(''); },
  });
  const rejectMutation = useMutation({
    mutationFn: (comments) => apiClient.rejectSAR({ id, comments }),
    onSuccess: () => { queryClient.invalidateQueries(['sar', id]); addAuditEntry('SAR_REJECTED', 'Rejected by officer'); setActionNotes(''); },
  });
  const requestInfoMutation = useMutation({
    mutationFn: (q) => apiClient.requestSARInfo({ id, question: q }),
    onSuccess: () => { queryClient.invalidateQueries(['sar', id]); addAuditEntry('INFO_REQUESTED', 'Investigator dispatched'); setQuestion(''); },
  });

  if (!id && !isLatestLoading && latestSars.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-center gap-3 text-slate-400">
        <FileText className="w-12 h-12 text-slate-700" />
        <h2 className="text-lg font-semibold text-slate-200">No SAR drafts pending</h2>
        <p className="text-sm max-w-md text-slate-500">
          SAR drafts are generated automatically when an entity crosses the critical risk threshold.
          Try injecting a critical event from the Admin Watchlist.
        </p>
        <Link to="/watchlist" className="mt-2 text-sm text-brand-400 hover:text-brand-300 flex items-center gap-1 transition-colors">
          Go to Admin Watchlist <ChevronRight className="w-4 h-4" />
        </Link>
      </div>
    );
  }

  if (isLoading || (!id && isLatestLoading)) {
    return <div className="flex h-full items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-brand-500" /></div>;
  }

  if (!sar) return null;

  const isPending = sar.status === 'DRAFT' || sar.status === 'PENDING_APPROVAL';

  return (
    <div className="flex h-full gap-5 max-w-7xl mx-auto w-full">

      {/* ── SAR List Sidebar ── */}
      <div className="w-52 shrink-0 glass-card rounded-2xl p-3 flex flex-col overflow-hidden">
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 px-1">SARs</h2>
        <div className="flex-1 overflow-y-auto space-y-1">
          {allSars.map(s => (
            <Link
              key={s.id}
              to={`/sar/${s.id}`}
              className={clsx(
                'block px-2.5 py-2 rounded-xl text-xs transition-all border',
                s.id === id
                  ? 'bg-brand-500/15 border-brand-500/30 text-brand-300'
                  : 'border-transparent text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
              )}
            >
              <p className="font-medium truncate">{s.entity_name || s.alert_id || s.id.slice(0, 12)}</p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className={clsx(
                  'px-1.5 py-0.5 rounded text-[10px] font-medium',
                  s.status === 'DRAFT'            ? 'text-amber-400 bg-amber-500/10' :
                  s.status === 'PENDING_APPROVAL' ? 'text-brand-400 bg-brand-500/10' :
                  s.status === 'APPROVED'         ? 'text-emerald-400 bg-emerald-500/10' :
                                                    'text-slate-400 bg-slate-800'
                )}>{s.status}</span>
                <span className="text-slate-600">v{s.version}</span>
              </div>
            </Link>
          ))}
          {allSars.length === 0 && <p className="text-xs text-slate-600 text-center py-6">No SARs yet</p>}
        </div>
      </div>

      {/* ── Main ── */}
      <div className="flex-1 flex flex-col gap-4 overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <FileText className="w-6 h-6 text-brand-400" />
              SAR Review
            </h1>
            <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
              <span className="font-mono">{sar.id?.slice(0, 16)}…</span>
              <span>·</span>
              <span className="text-slate-400">Alert: {sar.alert_id}</span>
              <span>·</span>
              <span className="bg-slate-800 text-brand-400 px-2 py-0.5 rounded font-mono">v{sar.version}</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <StatusStepper current={sar.status} />
            {isEditing ? (
              <>
                <button onClick={() => { setIsEditing(false); setDraftNarrative(sar.narrative); }}
                  className="px-3 py-1.5 rounded-xl text-sm text-slate-400 hover:text-slate-200 border border-slate-700 transition-colors">
                  Cancel
                </button>
                <button onClick={() => editMutation.mutate(draftNarrative)} disabled={editMutation.isPending}
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-sm font-medium transition-colors disabled:opacity-50">
                  {editMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  Save
                </button>
              </>
            ) : (
              isPending && (
                <button onClick={() => setIsEditing(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-700 bg-slate-800/50 hover:bg-slate-700/50 text-sm text-slate-300 hover:text-white transition-all">
                  <Edit3 className="w-3.5 h-3.5" /> Edit
                </button>
              )
            )}
          </div>
        </div>

        {/* Degraded warning */}
        {sar.degraded_draft && (
          <div className="flex items-start gap-3 px-4 py-3 rounded-xl border bg-amber-500/5 border-amber-500/20 text-amber-400">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <div className="text-xs">
              <p className="font-semibold">Degraded Mode</p>
              <p className="opacity-80 mt-0.5">Draft generated without LLM — template + retrieved passages only. Review carefully.</p>
            </div>
          </div>
        )}

        <div className="flex flex-1 gap-4 min-h-0 overflow-hidden">

          {/* Left: Narrative + Actions */}
          <div className="w-3/5 flex flex-col gap-4 overflow-hidden">
            <div className="glass-card rounded-2xl p-5 flex flex-col flex-1 min-h-0">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">Generated Narrative</h3>
              {isEditing ? (
                <textarea
                  className="flex-1 w-full bg-slate-950 border border-slate-700 rounded-xl p-4 text-slate-300 font-mono text-sm leading-relaxed focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none resize-none"
                  value={draftNarrative}
                  onChange={e => setDraftNarrative(e.target.value)}
                />
              ) : (
                <div className="flex-1 overflow-y-auto bg-slate-950 border border-slate-800/60 rounded-xl p-4 text-slate-300 text-sm leading-relaxed whitespace-pre-wrap font-serif">
                  {sar.narrative || 'No narrative generated.'}
                </div>
              )}
            </div>

            {isPending && (
              <div className="glass-card rounded-2xl p-5 space-y-3">
                <h3 className="text-sm font-semibold text-slate-300">Decision Actions</h3>
                <textarea
                  placeholder="Review notes (required for approve/reject)…"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-sm text-slate-300 h-16 resize-none focus:border-brand-500 outline-none"
                  value={actionNotes}
                  onChange={e => setActionNotes(e.target.value)}
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => rejectMutation.mutate(actionNotes)}
                    disabled={!actionNotes || rejectMutation.isPending}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-red-500/10 text-red-400 hover:bg-red-500/20 rounded-xl text-sm font-medium transition-colors disabled:opacity-40"
                  >
                    {rejectMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
                    Reject
                  </button>
                  <button
                    onClick={() => approveMutation.mutate(actionNotes)}
                    disabled={!actionNotes || approveMutation.isPending}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-brand-600 text-white hover:bg-brand-500 rounded-xl text-sm font-medium transition-colors disabled:opacity-40"
                  >
                    {approveMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                    Approve & File
                  </button>
                </div>
                <div className="flex gap-2 pt-2 border-t border-slate-800">
                  <input
                    type="text"
                    placeholder="Ask the Investigator a question…"
                    className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-slate-300 focus:border-brand-500 outline-none"
                    value={question}
                    onChange={e => setQuestion(e.target.value)}
                  />
                  <button
                    onClick={() => requestInfoMutation.mutate(question)}
                    disabled={!question || requestInfoMutation.isPending}
                    className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 text-slate-300 hover:text-white rounded-xl text-sm font-medium transition-colors disabled:opacity-40"
                  >
                    {requestInfoMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <MessageSquare className="w-4 h-4" />}
                    Ask
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Right: Evidence + Citations + Session */}
          <div className="w-2/5 flex flex-col gap-4 overflow-y-auto">
            {optimisticAudit.length > 0 && (
              <div className="glass-card rounded-2xl p-4">
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Session Activity</h3>
                <div className="space-y-2">
                  {optimisticAudit.map((entry, idx) => (
                    <div key={idx} className="flex gap-2.5 text-xs">
                      <Clock className="w-3 h-3 text-slate-600 mt-0.5 shrink-0" />
                      <div>
                        <span className="text-brand-400 font-medium">{entry.actor}</span>
                        <span className="text-slate-500"> · {entry.action}</span>
                        <p className="text-slate-400 text-[10px] mt-0.5">{entry.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="glass-card rounded-2xl p-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-brand-400" />
                Regulatory Citations
              </h3>
              <div className="flex flex-wrap gap-2">
                {sar.citations?.map((cit, idx) => (
                  <button
                    key={idx}
                    onClick={() => setSelectedCitation(selectedCitation === cit ? null : cit)}
                    className={clsx(
                      'px-2.5 py-1 rounded-full text-xs font-medium border transition-all',
                      selectedCitation === cit
                        ? 'bg-brand-500/20 border-brand-500/50 text-brand-300'
                        : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-300'
                    )}
                  >
                    {cit.source}
                  </button>
                ))}
                {(!sar.citations || sar.citations.length === 0) && (
                  <p className="text-xs text-slate-600">No citations attached.</p>
                )}
              </div>
              {selectedCitation && (
                <div className="mt-3 p-3 rounded-xl bg-slate-950 border border-brand-500/20 animate-fade-in">
                  <p className="text-xs font-bold text-brand-400 mb-1">{selectedCitation.source}</p>
                  <p className="text-xs text-slate-300 italic leading-relaxed">"{selectedCitation.context}"</p>
                </div>
              )}
            </div>

            <div className="glass-card rounded-2xl p-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">Compiled Evidence</h3>
              <EvidenceBundle
                evidence={sar.citations?.map(c => ({ source: c.source, snippet: c.context, relevance: 'Medium' })) || []}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
