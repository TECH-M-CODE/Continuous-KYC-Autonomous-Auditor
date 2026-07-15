import React from 'react';
import { Handle, Position } from '@xyflow/react';
import { FileText, ShieldAlert, Activity, CheckCircle, XCircle, ArrowRightLeft } from 'lucide-react';

const BaseNode = ({ data, selected, icon: Icon, colorClass, borderClass, bgClass, iconBgClass, targetPosition = Position.Left, sourcePosition = Position.Right }) => (
  <div className={`px-5 py-4 rounded-2xl border shadow-2xl w-72 backdrop-blur-md transition-all duration-300 ${selected ? 'ring-2 ring-brand-400 scale-105 z-10' : 'hover:scale-105 z-0'} ${bgClass} ${borderClass}`}>
    <Handle type="target" position={targetPosition} className="w-3 h-3 bg-brand-400 border-2 border-slate-900 rounded-full" />
    <div className="flex items-start gap-4">
      <div className={`p-2.5 rounded-xl ${colorClass} ${iconBgClass} shadow-inner`}>
        <Icon className="w-6 h-6" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">{data.kind}</div>
        <div className="text-sm font-bold text-slate-100 leading-snug break-words">{data.label}</div>
      </div>
    </div>
    <Handle type="source" position={sourcePosition} className="w-3 h-3 bg-brand-400 border-2 border-slate-900 rounded-full" />
  </div>
);

export const EventNode = (props) => (
  <BaseNode 
    {...props} 
    icon={FileText} 
    colorClass="text-blue-400" 
    borderClass="border-blue-500/30" 
    bgClass="bg-slate-900/80" 
    iconBgClass="bg-blue-500/20"
  />
);

export const ScreenNode = (props) => (
  <BaseNode 
    {...props} 
    icon={ShieldAlert} 
    colorClass="text-purple-400" 
    borderClass="border-purple-500/30" 
    bgClass="bg-slate-900/80" 
    iconBgClass="bg-purple-500/20"
  />
);

export const VerifyNode = (props) => (
  <BaseNode 
    {...props} 
    icon={CheckCircle} 
    colorClass="text-emerald-400" 
    borderClass="border-emerald-500/30" 
    bgClass="bg-slate-900/80" 
    iconBgClass="bg-emerald-500/20"
  />
);

export const ScoreNode = (props) => (
  <BaseNode 
    {...props} 
    icon={Activity} 
    colorClass="text-orange-400" 
    borderClass="border-orange-500/30" 
    bgClass="bg-slate-900/80" 
    iconBgClass="bg-orange-500/20"
  />
);

export const PropagateNode = (props) => (
  <BaseNode 
    {...props} 
    icon={ArrowRightLeft} 
    colorClass="text-cyan-400" 
    borderClass="border-cyan-500/30" 
    bgClass="bg-slate-900/80" 
    iconBgClass="bg-cyan-500/20"
  />
);

export const DecisionNode = ({ data, selected, targetPosition = Position.Left }) => {
  const isAlert = data.label.toLowerCase().includes('alert');
  const colorClass = isAlert ? 'text-red-400' : 'text-slate-400';
  const borderClass = isAlert ? 'border-red-500/40' : 'border-slate-600/40';
  const bgClass = isAlert ? 'bg-red-950/40' : 'bg-slate-800/80';
  const iconBgClass = isAlert ? 'bg-red-500/20' : 'bg-slate-500/20';
  const Icon = isAlert ? ShieldAlert : XCircle;

  return (
    <div className={`px-5 py-4 rounded-2xl border shadow-2xl w-72 backdrop-blur-md transition-all duration-300 ${selected ? 'ring-2 ring-brand-400 scale-105 z-10' : 'hover:scale-105 z-0'} ${bgClass} ${borderClass}`}>
      <Handle type="target" position={targetPosition} className="w-3 h-3 bg-brand-400 border-2 border-slate-900 rounded-full" />
      <div className="flex items-center gap-4">
        <div className={`p-2.5 rounded-xl ${colorClass} ${iconBgClass} shadow-inner`}>
          <Icon className="w-6 h-6" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Decision</div>
          <div className={`text-sm font-bold leading-snug break-words ${isAlert ? 'text-red-300' : 'text-slate-300'}`}>{data.label}</div>
        </div>
      </div>
    </div>
  );
};
