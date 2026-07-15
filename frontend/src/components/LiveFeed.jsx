import React, { useEffect, useRef, useState } from 'react';
import { useSSE } from '../hooks/useSSE';
import { Activity, Zap, ShieldAlert, ArrowRightLeft, AlertTriangle } from 'lucide-react';
import clsx from 'clsx';

const MAX_EVENTS = 40;

const EVENT_META = {
  'alert.new':        { icon: ShieldAlert, color: 'text-red-400',    bg: 'bg-red-500/10',    label: 'Alert' },
  'pipeline.start':   { icon: Zap,         color: 'text-brand-400',  bg: 'bg-brand-500/10',  label: 'Pipeline' },
  'pipeline.done':    { icon: Activity,     color: 'text-emerald-400',bg: 'bg-emerald-500/10',label: 'Done' },
  'transaction':      { icon: ArrowRightLeft,color:'text-yellow-400', bg: 'bg-yellow-500/10', label: 'Transaction' },
  default:            { icon: Activity,     color: 'text-slate-400',  bg: 'bg-slate-700/50',  label: 'Event' },
};

function getEventMeta(type = '') {
  return EVENT_META[type] || EVENT_META.default;
}

function timeStr() {
  return new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

/**
 * SSE-powered live event feed.
 * Renders up to MAX_EVENTS entries, newest at top, with slide-in animation.
 */
export const LiveFeed = ({ className = '', maxHeight = 320, showHeader = true }) => {
  const { lastEvent, connected } = useSSE();
  const [events, setEvents] = useState([]);
  const listRef = useRef(null);

  // Seed with a startup message
  useEffect(() => {
    setEvents([{
      id: 'seed',
      type: 'pipeline.start',
      message: 'SentinelAI pipeline connected — monitoring active.',
      time: timeStr(),
    }]);
  }, []);

  useEffect(() => {
    if (!lastEvent) return;
    const entry = {
      id: `${Date.now()}-${Math.random()}`,
      type: lastEvent.type || 'default',
      message: buildMessage(lastEvent),
      time: timeStr(),
    };
    setEvents(prev => [entry, ...prev].slice(0, MAX_EVENTS));
  }, [lastEvent]);

  function buildMessage(evt) {
    const d = evt.data;
    if (!d) return evt.type;
    if (evt.type === 'alert.new')
      return `New ${d.priority || ''} alert — ${d.entity_name || d.entity_id || 'unknown entity'}`;
    if (evt.type === 'pipeline.done')
      return `Pipeline done: ${d.entity_name || d.outcome || ''}`;
    return d.message || d.text || JSON.stringify(d).slice(0, 80);
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
          const meta = getEventMeta(evt.type);
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
                <p className="text-xs text-slate-300 truncate">{evt.message}</p>
              </div>
              <span className="text-xs text-slate-600 font-mono shrink-0">{evt.time}</span>
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
