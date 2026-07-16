import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Link } from 'react-router-dom';
import { useSSE } from '../hooks/useSSE';
import {
  Loader2, Check, X, Radio, Newspaper, Building2,
  ShieldAlert, Scale, Gauge, FileText, CheckCircle2, ChevronRight
} from 'lucide-react';
import clsx from 'clsx';

// Ordered to match the backend agent graph (see supervisor._build_graph).
const STAGES = [
  { key: 'monitor',      label: 'Ingesting event',              icon: Radio },
  { key: 'news',         label: 'Enriching from news & data',   icon: Newspaper },
  { key: 'entity',       label: 'Resolving entity',             icon: Building2 },
  { key: 'sanctions',    label: 'Screening watchlists',         icon: ShieldAlert },
  { key: 'resolver',     label: 'Adjudicating match',           icon: Scale },
  { key: 'investigator', label: 'Scoring risk',                 icon: Gauge },
  { key: 'reporter',     label: 'Drafting SAR & alert',         icon: FileText },
];

const stageIndex = (key) => STAGES.findIndex(s => s.key === key);

export const PipelineProgress = ({ open, onClose, expectedCount = 1, entityName }) => {
  const { lastEvent } = useSSE();
  const [current, setCurrent] = useState(0);
  const [done, setDone] = useState(0);
  const seen = useRef(null);

  // Reset when (re)opened.
  useEffect(() => {
    if (open) { setCurrent(0); setDone(0); seen.current = null; }
  }, [open]);

  // Drive the stepper from real backend progress frames.
  useEffect(() => {
    if (!open || !lastEvent || lastEvent === seen.current) return;
    if (lastEvent.type !== 'pipeline.progress') return;
    seen.current = lastEvent;
    const idx = stageIndex(lastEvent.data?.stage);
    if (idx < 0) return;
    setCurrent(idx);
    if (lastEvent.data?.stage === 'reporter') {
      setDone(d => d + 1);
    }
  }, [lastEvent, open]);

  const allDone = done >= expectedCount;

  // Safety valve: never let the overlay hang forever.
  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => setDone(expectedCount), 120000);
    return () => clearTimeout(t);
  }, [open, expectedCount]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-md">
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        className="glass-card border-brand-500/20 rounded-2xl shadow-2xl w-full max-w-md p-6"
      >
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            {allDone
              ? <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              : <Loader2 className="w-5 h-5 text-brand-400 animate-spin" />}
            {allDone ? 'Analysis complete' : 'Agents at work…'}
          </h3>
          {allDone && (
            <button onClick={onClose} className="text-slate-500 hover:text-slate-200">
              <X className="w-5 h-5" />
            </button>
          )}
        </div>
        <p className="text-xs text-slate-500 mb-5">
          {entityName ? <>Running the KYC pipeline for <span className="text-slate-300 font-medium">{entityName}</span>.</> : 'Running the KYC pipeline.'}
          {expectedCount > 1 && <> · {Math.min(done + (allDone ? 0 : 1), expectedCount)}/{expectedCount} events</>}
        </p>

        <div className="space-y-1">
          {STAGES.map((stage, i) => {
            const isDone = allDone || i < current;
            const isActive = !allDone && i === current;
            const Icon = stage.icon;
            return (
              <div
                key={stage.key}
                className={clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-xl border transition-all',
                  isActive ? 'bg-brand-500/10 border-brand-500/30'
                    : isDone ? 'bg-emerald-500/5 border-emerald-500/15'
                    : 'bg-slate-800/30 border-slate-800'
                )}
              >
                <div className={clsx(
                  'w-7 h-7 rounded-lg flex items-center justify-center shrink-0',
                  isActive ? 'bg-brand-500/20' : isDone ? 'bg-emerald-500/15' : 'bg-slate-800'
                )}>
                  {isDone
                    ? <Check className="w-4 h-4 text-emerald-400" />
                    : isActive
                      ? <Loader2 className="w-4 h-4 text-brand-400 animate-spin" />
                      : <Icon className="w-4 h-4 text-slate-600" />}
                </div>
                <span className={clsx(
                  'text-sm font-medium flex-1',
                  isActive ? 'text-brand-200' : isDone ? 'text-emerald-300/80' : 'text-slate-500'
                )}>
                  {stage.label}
                </span>
              </div>
            );
          })}
        </div>

        {allDone && (
          <Link
            to="/alerts"
            onClick={onClose}
            className="mt-5 w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-sm font-semibold transition-colors"
          >
            View Alert Queue <ChevronRight className="w-4 h-4" />
          </Link>
        )}
      </motion.div>
    </div>
  );
};
