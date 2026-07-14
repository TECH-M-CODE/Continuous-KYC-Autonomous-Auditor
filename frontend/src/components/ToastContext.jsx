import React, { createContext, useContext, useState, useCallback } from 'react';
import { FileText, AlertTriangle, Info, CheckCircle, X } from 'lucide-react';
import { Link } from 'react-router-dom';

const ToastContext = createContext(null);

export const ToastProvider = ({ children }) => {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((toast) => {
    const id = Date.now().toString();
    setToasts((prev) => [...prev, { ...toast, id }]);
    if (toast.duration !== Infinity) {
      setTimeout(() => {
        removeToast(id);
      }, toast.duration || 5000);
    }
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ addToast, removeToast }}>
      {children}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3 pointer-events-none">
        {toasts.map((t) => (
          <div key={t.id} className="pointer-events-auto bg-slate-900 border border-slate-700 p-4 rounded-lg shadow-xl min-w-[300px] flex items-start gap-3 animate-in slide-in-from-right">
            {t.type === 'sar' && <FileText className="w-5 h-5 text-orange-400 shrink-0" />}
            {t.type === 'alert' && <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />}
            {t.type === 'success' && <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0" />}
            {!['sar', 'alert', 'success'].includes(t.type) && <Info className="w-5 h-5 text-brand-400 shrink-0" />}
            
            <div className="flex-1">
              <h4 className="text-sm font-semibold text-slate-100">{t.title}</h4>
              <p className="text-xs text-slate-400 mt-1">{t.message}</p>
              {t.actionLink && t.actionText && (
                <Link 
                  to={t.actionLink} 
                  className="inline-block mt-2 text-xs font-medium text-brand-400 hover:text-brand-300"
                  onClick={() => removeToast(t.id)}
                >
                  {t.actionText} &rarr;
                </Link>
              )}
            </div>
            
            <button onClick={() => removeToast(t.id)} className="text-slate-500 hover:text-slate-300">
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = () => useContext(ToastContext);
