import React from 'react';
import { Database, FileText, Link as LinkIcon } from 'lucide-react';
import { StatusBadge } from './StatusBadge';

export const EvidenceBundle = ({ evidence = [] }) => {
  if (!evidence || evidence.length === 0) {
    return (
      <div className="p-4 bg-slate-900 rounded-lg border border-slate-800 text-center">
        <p className="text-sm text-slate-500">No evidence items available.</p>
      </div>
    );
  }

  const relevanceScore = {
    'Critical': 4,
    'High': 3,
    'Medium': 2,
    'Low': 1
  };

  const sortedEvidence = [...evidence].sort((a, b) => 
    (relevanceScore[b.relevance] || 0) - (relevanceScore[a.relevance] || 0)
  );

  return (
    <div className="space-y-3">
      {sortedEvidence.map((item, idx) => (
        <div key={idx} className="p-4 bg-slate-900 rounded-lg border border-slate-800 flex gap-4">
          <div className="w-10 h-10 shrink-0 bg-slate-800 rounded flex items-center justify-center text-slate-400">
            {item.source === 'Reuters' || item.source.includes('Media') ? (
              <FileText className="w-5 h-5" />
            ) : item.source.includes('SAML') ? (
              <Database className="w-5 h-5" />
            ) : (
              <LinkIcon className="w-5 h-5" />
            )}
          </div>
          
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-semibold text-brand-400 uppercase tracking-wider">{item.source}</span>
              <StatusBadge status={item.relevance.toLowerCase()} label={item.relevance} />
            </div>
            <p className="text-sm text-slate-200 mt-2 italic border-l-2 border-slate-700 pl-3">
              "{item.snippet}"
            </p>
          </div>
        </div>
      ))}
    </div>
  );
};
