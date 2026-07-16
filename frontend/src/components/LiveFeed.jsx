import React, { useEffect, useRef, useState } from 'react';
import { useSSE } from '../hooks/useSSE';
import {
  Activity, Zap, ShieldAlert, FileText, TrendingUp, Search,
  Newspaper, Building2, Scale, Gauge, Radio
} from 'lucide-react';
import clsx from 'clsx';

const EVENT_META = {
  'alert.new':         { icon: ShieldAlert, color: 'text-red-400',     bg: 'bg-red-500/10' },
  'alert.updated':     { icon: ShieldAlert, color: 'text-amber-400',   bg: 'bg-amber-500/10' },
  'sar.ready':         { icon: FileText,    color: 'text-orange-400',  bg: 'bg-orange-500/10' },
  'entity.updated':    { icon: TrendingUp,  color: 'text-brand-400',   bg: 'bg-brand-500/10' },
  'pipeline.progress': { icon: Zap,         color: 'text-brand-400',   bg: 'bg-brand-500/10' },
  'system.health':     { icon: Activity,    color: 'text-yellow-400',  bg: 'bg-yellow-500/10' },
  default:             { icon: Activity,    color: 'text-slate-400',   bg: 'bg-slate-700/50' },
};

// Per-agent icons so the feed reads like a pipeline, not a log dump.
const STAGE_ICON = {
  monitor: Radio, news: Newspaper, entity: Building2,
  sanctions: Search, resolver: Scale, investigator: Gauge, reporter: FileText,
};

function getEventMeta(evt) {
  const base = EVENT_META[evt.type] || EVENT_META.default;
  if (evt.type === 'pipeline.progress') {
    const Icon = STAGE_ICON[evt.data?.stage];
    if (Icon) return { ...base, icon: Icon };
  }
  return base;
}

/**
 * SSE-powered live event feed.
 * Renders up to MAX_EVENTS entries, newest at top, with slide-in animation.
 */
export const LiveFeed = ({ className = '', maxHeight = 320, showHeader = true }) => {
  const { connected, events } = useSSE();
  const listRef = useRef(null);

  // Every branch must produce a plain-English sentence — never raw JSON.
  function buildMessage(evt) {
    const d = evt.data || {};
    const who = d.entity_name || d.entity_id || 'an entity';

    switch (evt.type) {
      case 'pipeline.progress':
        return d.entity_name
          ? `${d.label || 'Processing'} — ${d.entity_name}`
          : `${d.label || 'Processing event'}`;
      case 'alert.new':
        return `${(d.priority || 'New').toString().toLowerCase()} alert raised for ${who}`;
      case 'alert.updated':
        return `Alert for ${who} updated${d.status ? ` to ${d.status.toLowerCase()}` : ''}`;
      case 'sar.ready':
        return `SAR draft ready for review — ${who}`;
      case 'entity.updated':
        return d.new_risk_score != null
          ? `${who} risk score is now ${Math.round(d.new_risk_score)}${d.risk_band ? ` (${d.risk_band.toLowerCase()})` : ''}`
          : `${who} was updated`;
      case 'system.health':
        return `${d.adapter || 'A data feed'} is ${d.status || 'degraded'}`;
      default:
        return d.message || d.text || d.label || 'Pipeline event';
    }
  }

  return (
    <div className={clsx('flex flex-col', className)}>
      {showHeader && (
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <Activity className="w-4 h-4 text-brand-400" />
            Live Pipeline Feed
          </h3>
          <span className={clsx(
            'flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full border',
            connected
              ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
              : 'text-red-400 bg-red-500/10 border-red-500/20'
          )}>
            <span className={clsx('w-1.5 h-1.5 rounded-full', connected ? 'bg-emerald-400 animate-ping' : 'bg-red-400')} />
            {connected ? 'Live' : 'Disconnected'}
          </span>
        </div>
      )}

      <div
        ref={listRef}
        className="overflow-y-auto space-y-1.5 pr-1"
        style={{ maxHeight }}
      >
        {events.map((evt, i) => {
          const meta = getEventMeta(evt);
          const Icon = meta.icon;
          return (
            <div
              key={evt.id}
              className={clsx(
                'flex items-start gap-3 p-2.5 rounded-lg border border-transparent',
                'animate-slide-up',
                i === 0 && 'border-brand-500/20 bg-brand-500/5',
              )}
              style={{ animationDelay: `${i === 0 ? 0 : i * 20}ms` }}
            >
              <div className={clsx('p-1 rounded', meta.bg, 'shrink-0 mt-0.5')}>
                <Icon className={clsx('w-3 h-3', meta.color)} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-slate-300 truncate">{buildMessage(evt)}</p>
              </div>
              <span className="text-xs text-slate-600 font-mono shrink-0">
                {new Date(evt.timestamp).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            </div>
          );
        })}
        {events.length === 0 && (
          <p className="text-xs text-slate-600 text-center py-8">Waiting for pipeline events…</p>
        )}
      </div>
    </div>
  );
};

export default LiveFeed;
