import React, { useState } from 'react';
import { Link2, CheckCircle, XCircle, Copy, Check } from 'lucide-react';
import clsx from 'clsx';

function truncate(str = '', n = 10) {
  return str.length > n ? `${str.slice(0, n)}…` : str;
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {}
  };
  return (
    <button
      onClick={handleCopy}
      title="Copy hash"
      className="p-1 text-slate-600 hover:text-slate-300 transition-colors"
    >
      {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
    </button>
  );
}

/**
 * Visual blockchain-style hash chain row display.
 * Expects `entries` array: [{ id, seq, actor, action, prev_hash, entry_hash, created_at, timestamp }]
 * `isValid` boolean from /audit/verify
 */
export const HashChain = ({ entries = [], isValid = true }) => {
  const [expanded, setExpanded] = useState(null);

  return (
    <div className="space-y-0">
      {entries.map((entry, idx) => {
        const prevHash  = entry.prev_hash || entry.previous_hash || '';
        const entryHash = entry.entry_hash || '';
        const isFirst   = idx === entries.length - 1;
        const isNew     = idx === 0;
        const actorColor =
          entry.actor === 'human'  ? 'text-emerald-400' :
          entry.actor === 'system' ? 'text-purple-400'  : 'text-brand-400';

        return (
          <div key={entry.id || idx} className={clsx('relative', !isFirst && 'pt-0')}>
            {/* Chain connector line */}
            {!isFirst && (
              <div className="absolute left-[27px] top-0 bottom-1/2 w-px bg-gradient-to-b from-slate-700 to-transparent" />
            )}
            {idx !== 0 && (
              <div className="absolute left-[27px] top-1/2 bottom-0 w-px bg-gradient-to-b from-transparent to-slate-700" />
            )}

            <div
              className={clsx(
                'relative flex items-start gap-4 p-4 rounded-xl border transition-all cursor-pointer',
                isNew
                  ? 'border-brand-500/30 bg-brand-500/5'
                  : 'border-slate-800/80 bg-slate-900/50 hover:border-slate-700 hover:bg-slate-800/30',
                expanded === idx && 'border-slate-600'
              )}
              onClick={() => setExpanded(expanded === idx ? null : idx)}
            >
              {/* Chain link icon */}
              <div className={clsx(
                'relative z-10 w-9 h-9 rounded-lg flex items-center justify-center shrink-0 border',
                isFirst
                  ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                  : 'bg-slate-800 border-slate-700 text-slate-500',
              )}>
                <Link2 className="w-4 h-4" />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="text-xs font-mono text-brand-400 font-semibold">#{entry.seq ?? idx}</span>
                  <span className={clsx('text-xs font-semibold uppercase tracking-wider', actorColor)}>{entry.actor}</span>
                  <span className="text-sm font-medium text-slate-200">{entry.action}</span>
                  <span className="text-xs text-slate-500 ml-auto">
                    {new Date(entry.created_at || entry.timestamp).toLocaleTimeString()}
                  </span>
                </div>

                {/* Hash preview */}
                <div className="flex items-center gap-4 mt-2 font-mono text-xs text-slate-500">
                  {!isFirst && prevHash && (
                    <span className="flex items-center gap-1">
                      <span className="text-slate-600">← prev</span>
                      <code className="text-slate-400">{truncate(prevHash, 12)}</code>
                    </span>
                  )}
                  {isFirst && (
                    <span className="text-slate-600 italic">genesis block</span>
                  )}
                  <span className="flex items-center gap-1">
                    <span className="text-slate-600">hash</span>
                    <code className="text-brand-500/80">{truncate(entryHash, 12)}</code>
                    <CopyButton text={entryHash} />
                  </span>
                </div>

                {/* Expanded: full hashes */}
                {expanded === idx && (
                  <div className="mt-3 p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2 animate-fade-in">
                    {prevHash && (
                      <div className="flex items-center gap-2 text-xs">
                        <span className="text-slate-500 w-20 shrink-0">prev_hash</span>
                        <code className="text-slate-400 break-all font-mono text-xs">{prevHash}</code>
                        <CopyButton text={prevHash} />
                      </div>
                    )}
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-slate-500 w-20 shrink-0">entry_hash</span>
                      <code className="text-brand-400 break-all font-mono text-xs">{entryHash}</code>
                      <CopyButton text={entryHash} />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default HashChain;
