import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { ShieldCheck, ShieldAlert, Loader2 } from 'lucide-react';
import { apiClient } from '../api/client';
import clsx from 'clsx';

export const ChainVerifyBadge = () => {
  const [result, setResult] = useState(null);

  const mutation = useMutation({
    mutationFn: apiClient.verifyAuditChain,
    onSuccess: (data) => {
      setResult(data);
    }
  });

  if (result) {
    if (result.valid) {
      return (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 text-emerald-400 rounded-lg border border-emerald-500/20 text-sm font-medium">
          <ShieldCheck className="w-4 h-4" />
          Chain intact — {result.checked} entries verified
        </div>
      );
    } else {
      return (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-red-500/10 text-red-400 rounded-lg border border-red-500/20 text-sm font-medium">
          <ShieldAlert className="w-4 h-4" />
          Chain broken — failure at sequence {result.first_bad_seq}
        </div>
      );
    }
  }

  return (
    <button
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
      className={clsx(
        "flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-medium transition-colors",
        "bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-slate-100",
        mutation.isPending && "opacity-50 cursor-not-allowed"
      )}
    >
      {mutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
      Verify Chain
    </button>
  );
};
