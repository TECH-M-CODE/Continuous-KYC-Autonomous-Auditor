import React from 'react';
import { Handle, Position } from '@xyflow/react';
import { FileText, ShieldAlert, Activity, CheckCircle, XCircle, ArrowRightLeft } from 'lucide-react';

const BaseNode = ({ data, selected, icon: Icon, colorClass, borderClass, bgClass }) => (
  <div className={`px-4 py-3 rounded-lg border-2 shadow-lg w-64 ${selected ? 'ring-2 ring-brand-400' : ''} ${bgClass} ${borderClass}`}>
    <Handle type="target" position={Position.Left} className="w-2 h-2 bg-slate-500 border-none" />
    <div className="flex items-start gap-3">
      <div className={`p-2 rounded-md ${colorClass} bg-opacity-10 bg-current`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">{data.kind}</div>
        <div className="text-sm font-bold text-slate-200 leading-tight">{data.label}</div>
      </div>
    </div>
    <Handle type="source" position={Position.Right} className="w-2 h-2 bg-slate-500 border-none" />
  </div>
);

export const EventNode = (props) => (
  <BaseNode 
    {...props} 
    icon={FileText} 
    colorClass="text-blue-400" 
    borderClass="border-blue-900" 
    bgClass="bg-slate-900" 
  />
);

export const ScreenNode = (props) => (
  <BaseNode 
    {...props} 
    icon={ShieldAlert} 
    colorClass="text-purple-400" 
    borderClass="border-purple-900" 
    bgClass="bg-slate-900" 
  />
);

export const VerifyNode = (props) => (
  <BaseNode 
    {...props} 
    icon={CheckCircle} 
    colorClass="text-emerald-400" 
    borderClass="border-emerald-900" 
    bgClass="bg-slate-900" 
  />
);

export const ScoreNode = (props) => (
  <BaseNode 
    {...props} 
    icon={Activity} 
    colorClass="text-orange-400" 
    borderClass="border-orange-900" 
    bgClass="bg-slate-900" 
  />
);

export const PropagateNode = (props) => (
  <BaseNode 
    {...props} 
    icon={ArrowRightLeft} 
    colorClass="text-cyan-400" 
    borderClass="border-cyan-900" 
    bgClass="bg-slate-900" 
  />
);

export const DecisionNode = ({ data, selected }) => {
  const isAlert = data.label.toLowerCase().includes('alert');
  const colorClass = isAlert ? 'text-red-400' : 'text-slate-400';
  const borderClass = isAlert ? 'border-red-900' : 'border-slate-700';
  const bgClass = isAlert ? 'bg-red-950/30' : 'bg-slate-800/50';
  const Icon = isAlert ? ShieldAlert : XCircle;

  return (
    <div className={`px-4 py-3 rounded-lg border-2 shadow-lg w-64 ${selected ? 'ring-2 ring-brand-400' : ''} ${bgClass} ${borderClass}`}>
      <Handle type="target" position={Position.Left} className="w-2 h-2 bg-slate-500 border-none" />
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-md ${colorClass} bg-opacity-10 bg-current`}>
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">Decision</div>
          <div className={`text-sm font-bold ${isAlert ? 'text-red-300' : 'text-slate-300'}`}>{data.label}</div>
        </div>
      </div>
    </div>
  );
};
