'use client';

import { useState } from 'react';
import UploadForm from './components/UploadForm';
import ResultsDashboard from './components/ResultsDashboard';
import { ScreeningResult } from './types/contracts';
import { ShieldAlert, RotateCcw, AlertOctagon, Activity } from 'lucide-react';

export default function Home() {
  const [screeningResult, setScreeningResult] = useState<ScreeningResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showResults, setShowResults] = useState(false);

  const handleResult = (result: ScreeningResult) => {
    setScreeningResult(result);
    setShowResults(true);
    setError(null);
  };

  const handleError = (errorMsg: string) => {
    setError(errorMsg);
    setShowResults(false);
  };

  const resetForm = () => {
    setScreeningResult(null);
    setShowResults(false);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 font-sans selection:bg-blue-500/30">
      {/* HEADER */}
      <header className="bg-slate-950 border-b border-slate-800 shadow-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/10 rounded-lg border border-blue-500/20">
              <ShieldAlert className="w-6 h-6 text-blue-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-slate-100">Identity Screening</h1>
              <p className="text-xs font-medium text-slate-400 tracking-wider uppercase">Officer Workstation</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-slate-900 rounded-md border border-slate-800">
              <Activity className="w-4 h-4 text-emerald-500" />
              <span className="text-xs font-medium text-slate-300">System Online</span>
            </div>
            {showResults && (
              <button
                onClick={resetForm}
                className="flex items-center gap-2 px-4 py-2 bg-slate-800 text-slate-200 border border-slate-700 rounded-md hover:bg-slate-700 hover:text-white transition-colors text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              >
                <RotateCcw className="w-4 h-4" />
                New Screening
              </button>
            )}
          </div>
        </div>
      </header>

      {/* MAIN CONTENT */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        {/* ERROR BANNER */}
        {error && (
          <div className="mb-6 p-4 bg-red-950/50 border border-red-900/50 rounded-lg flex items-start gap-3 shadow-sm">
            <AlertOctagon className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-semibold text-red-200 text-sm">System Error</p>
              <p className="text-sm text-red-300/80 mt-1">{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-400 hover:text-red-300 p-1 rounded-md hover:bg-red-900/30 transition-colors"
              aria-label="Dismiss error"
            >
              ✕
            </button>
          </div>
        )}

        {/* CONDITIONAL RENDER */}
        {!showResults ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-300 ease-out">
            <div className="max-w-4xl mx-auto mb-8 text-center">
              <h2 className="text-2xl font-bold text-slate-100 tracking-tight">
                Document & Subject Ingestion
              </h2>
              <p className="text-slate-400 mt-2 text-sm">
                Provide both the identity document and a live capture of the subject for automated verification.
              </p>
            </div>
            <UploadForm onResult={handleResult} onError={handleError} />
          </div>
        ) : screeningResult ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 ease-out">
            <ResultsDashboard result={screeningResult} />
          </div>
        ) : null}
      </main>

      {/* FOOTER */}
      <footer className="mt-auto py-6 border-t border-slate-800/50 text-center text-xs text-slate-500 font-medium">
        <p>AI Document Screening System v2.0 • Authorized Personnel Only</p>
      </footer>
    </div>
  );
}
