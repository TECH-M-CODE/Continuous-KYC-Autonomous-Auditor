import React, { useState } from 'react';
import { FileText, CheckCircle, XCircle, Edit3, BookOpen, ExternalLink } from 'lucide-react';

const mockSAR = {
  id: 'sar-991',
  alert_id: 'al-101',
  entity_id: 'ent-881',
  entity_name: 'Acme Holdings LLC',
  version: 1,
  status: 'pending_review',
  created_at: new Date().toISOString(),
  narrative: `This Suspicious Activity Report (SAR) is being filed for Acme Holdings LLC based on a combination of adverse media and structurally anomalous transactions.

On July 14, 2026, the entity was named in a fraud investigation by Reuters. Shortly after, the entity initiated multiple large wire transfers to high-risk jurisdictions, structured to avoid standard reporting thresholds.

The combination of events exceeds our critical risk threshold and indicates potential money laundering or sanctions evasion activities.`,
  regulatory_basis: [
    { citation: 'GDPR Article 30', passage: 'Records of processing activities must be maintained.' },
    { citation: 'BSA / AML § 1020.320', passage: 'Reports by banks of suspicious transactions.' }
  ],
  evidence: [
    { source: 'Reuters', snippet: 'Acme Holdings named in fraud probe', relevance: 'High' },
    { source: 'SAML-D', snippet: 'Large wire transfer to high-risk jurisdiction', relevance: 'Critical' }
  ]
};

export const SARReview = () => {
  const [narrative, setNarrative] = useState(mockSAR.narrative);
  const [isEditing, setIsEditing] = useState(false);
  const [status, setStatus] = useState(mockSAR.status); // purely visual for now

  return (
    <div className="flex flex-col h-full space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100 flex items-center gap-2">
            <FileText className="w-6 h-6 text-brand-400" />
            SAR Review
          </h1>
          <p className="text-sm text-slate-400 mt-1">Draft ID: {mockSAR.id} • Entity: {mockSAR.entity_name} • Version {mockSAR.version}</p>
        </div>
        
        <div className="flex items-center gap-3">
          <button 
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 text-slate-300 hover:text-slate-100 rounded-lg text-sm font-medium transition-colors"
            onClick={() => setIsEditing(!isEditing)}
          >
            <Edit3 className="w-4 h-4" />
            {isEditing ? 'Cancel Edit' : 'Edit Narrative'}
          </button>
          <button 
            className="flex items-center gap-2 px-4 py-2 bg-red-500/10 text-red-400 hover:bg-red-500/20 rounded-lg text-sm font-medium transition-colors"
            onClick={() => setStatus('rejected')}
          >
            <XCircle className="w-4 h-4" />
            Reject
          </button>
          <button 
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white hover:bg-brand-500 rounded-lg text-sm font-medium transition-colors"
            onClick={() => setStatus('approved')}
          >
            <CheckCircle className="w-4 h-4" />
            Approve & File
          </button>
        </div>
      </div>

      {status !== 'pending_review' && (
        <div className={`p-4 rounded-lg border ${status === 'approved' ? 'bg-green-500/10 border-green-500/20 text-green-400' : 'bg-red-500/10 border-red-500/20 text-red-400'}`}>
          This SAR has been {status}. (Mock action recorded)
        </div>
      )}

      <div className="flex flex-1 gap-6 min-h-[500px]">
        {/* Left Pane: Narrative */}
        <div className="w-2/3 bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col">
          <h3 className="text-lg font-medium text-slate-200 mb-4">Generated Narrative</h3>
          {isEditing ? (
            <textarea
              className="flex-1 w-full bg-slate-950 border border-slate-700 rounded-lg p-4 text-slate-300 font-mono text-sm leading-relaxed focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none resize-none"
              value={narrative}
              onChange={(e) => setNarrative(e.target.value)}
            />
          ) : (
            <div className="flex-1 w-full bg-slate-950 border border-slate-800 rounded-lg p-4 text-slate-300 font-serif text-base leading-relaxed overflow-y-auto whitespace-pre-wrap">
              {narrative}
            </div>
          )}
        </div>

        {/* Right Pane: Evidence & Citations */}
        <div className="w-1/3 space-y-6 overflow-y-auto">
          {/* Regulatory Basis */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-brand-400" />
              Regulatory Basis
            </h3>
            <div className="space-y-4">
              {mockSAR.regulatory_basis.map((reg, idx) => (
                <div key={idx} className="bg-slate-800/50 rounded p-3 border border-slate-700/50">
                  <div className="text-xs font-semibold text-slate-300 mb-1">{reg.citation}</div>
                  <div className="text-xs text-slate-500 italic">"{reg.passage}"</div>
                </div>
              ))}
            </div>
          </div>

          {/* Evidence List */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
              <ExternalLink className="w-4 h-4 text-brand-400" />
              Linked Evidence
            </h3>
            <div className="space-y-3">
              {mockSAR.evidence.map((ev, idx) => (
                <div key={idx} className="flex flex-col gap-1 pb-3 border-b border-slate-800 last:border-0 last:pb-0">
                  <div className="flex justify-between">
                    <span className="text-xs font-medium text-slate-400 uppercase">{ev.source}</span>
                    <span className="text-[10px] bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded">{ev.relevance} Relevance</span>
                  </div>
                  <div className="text-sm text-slate-300">{ev.snippet}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
