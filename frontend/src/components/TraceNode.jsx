import React from 'react';
import { Handle, Position } from '@xyflow/react';
import { FileText, ShieldAlert, Activity, CheckCircle, XCircle, ArrowRightLeft } from 'lucide-react';

const BaseNode = ({ data, selected, icon: Icon, colorClass, borderClass, bgClass }) => (
  <div className={`px-4 py-3 rounded-xl border-2 shadow-sm w-64 ${selected ? 'ring-2 ring-brand-500 border-brand-500' : ''} ${bgClass} ${borderClass} transition-all`}>
    <Handle type="target" position={Position.Left} className="w-2 h-2 bg-brand-400 border-none" />
    <div className="flex items-start gap-3">
      <div className={`p-2 rounded-lg ${colorClass} bg-opacity-10 bg-current border border-current/20 shadow-inner`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">{data.kind}</div>
        <div className="text-sm font-bold text-slate-800 leading-tight">{data.label}</div>
      </div>
    </div>
    <Handle type="source" position={Position.Right} className="w-2 h-2 bg-brand-400 border-none" />
  </div>
);

export const EventNode = (props) => (
  <BaseNode 
    {...props} 
    icon={FileText} 
    colorClass="text-blue-500" 
    borderClass="border-blue-200" 
    bgClass="bg-white/80 backdrop-blur-md" 
  />
);

export const ScreenNode = (props) => (
  <BaseNode 
    {...props} 
    icon={ShieldAlert} 
    colorClass="text-purple-500" 
    borderClass="border-purple-200" 
    bgClass="bg-white/80 backdrop-blur-md" 
  />
);

export const VerifyNode = (props) => (
  <BaseNode 
    {...props} 
    icon={CheckCircle} 
    colorClass="text-emerald-500" 
    borderClass="border-emerald-200" 
    bgClass="bg-white/80 backdrop-blur-md" 
  />
);

export const ScoreNode = (props) => (
  <BaseNode 
    {...props} 
    icon={Activity} 
    colorClass="text-orange-500" 
    borderClass="border-orange-200" 
    bgClass="bg-white/80 backdrop-blur-md" 
  />
);

export const PropagateNode = (props) => (
  <BaseNode 
    {...props} 
    icon={ArrowRightLeft} 
    colorClass="text-cyan-500" 
    borderClass="border-cyan-200" 
    bgClass="bg-white/80 backdrop-blur-md" 
  />
);

export const DecisionNode = ({ data, selected }) => {
  const isAlert = data.label.toLowerCase().includes('alert');
  const colorClass = isAlert ? 'text-red-500' : 'text-slate-500';
  const borderClass = isAlert ? 'border-red-300' : 'border-slate-300';
  const bgClass = isAlert ? 'bg-red-50/80 backdrop-blur-md' : 'bg-white/80 backdrop-blur-md';
  const Icon = isAlert ? ShieldAlert : XCircle;

  return (
    <div className={`px-4 py-3 rounded-xl border-2 shadow-sm w-64 ${selected ? 'ring-2 ring-brand-500 border-brand-500' : ''} ${bgClass} ${borderClass} transition-all`}>
      <Handle type="target" position={Position.Left} className="w-2 h-2 bg-brand-400 border-none" />
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${colorClass} bg-opacity-10 bg-current border border-current/20 shadow-inner`}>
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">Decision</div>
          <div className={`text-sm font-bold ${isAlert ? 'text-red-600' : 'text-slate-700'}`}>{data.label}</div>
        </div>
      </div>
    </div>
  );
};
