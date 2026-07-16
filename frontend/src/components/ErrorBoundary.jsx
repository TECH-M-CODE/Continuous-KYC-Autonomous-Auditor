import React from 'react';

/**
 * Without a boundary, any uncaught render error unmounts the entire React tree —
 * the page goes permanently blank and only a manual reload brings it back. This
 * catches it, keeps the app usable, and shows what actually broke.
 */
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('UI crash caught by ErrorBoundary:', error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="min-h-screen flex items-center justify-center p-6" style={{ background: 'var(--app-bg)' }}>
        <div className="glass-card rounded-2xl p-6 max-w-lg w-full">
          <h1 className="text-lg font-bold text-red-400 mb-2">Something broke in the UI</h1>
          <p className="text-sm text-slate-400 mb-4">
            The dashboard hit a rendering error. The rest of the system is unaffected —
            your data and the pipeline are still running.
          </p>
          <pre className="text-xs text-slate-400 bg-slate-950 border border-slate-800 rounded-xl p-3 overflow-auto max-h-48 whitespace-pre-wrap">
            {String(this.state.error?.message || this.state.error)}
          </pre>
          <div className="flex gap-2 mt-4">
            <button
              onClick={() => this.setState({ error: null })}
              className="px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-sm font-semibold transition-colors"
            >
              Try again
            </button>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 rounded-xl border border-slate-700 text-slate-300 hover:text-white text-sm transition-colors"
            >
              Reload page
            </button>
          </div>
        </div>
      </div>
    );
  }
}
