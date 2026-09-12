'use client';

import { useState } from 'react';
import UploadForm from './components/UploadForm';
import ResultsDashboard from './components/ResultsDashboard';
import { ScreeningResult } from './types/contracts';
import { Shield, RotateCcw, AlertCircle } from 'lucide-react';

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
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-gray-100">
      {/* HEADER */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Shield className="w-8 h-8 text-blue-600" />
            <div>
              <h1 className="text-2xl font-bold text-gray-900">AI Document Screening</h1>
              <p className="text-sm text-gray-500">Immigration Officer Portal</p>
            </div>
          </div>
          {showResults && (
            <button
              onClick={resetForm}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
            >
              <RotateCcw className="w-4 h-4" />
              New Screening
            </button>
          )}
        </div>
      </header>

      {/* MAIN CONTENT */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* ERROR BANNER */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-red-800">Error</p>
              <p className="text-sm text-red-700">{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="ml-auto text-red-600 hover:text-red-800"
            >
              ✕
            </button>
          </div>
        )}

        {/* CONDITIONAL RENDER */}
        {!showResults ? (
          <div>
            <h2 className="text-xl font-semibold text-gray-800 mb-6 text-center">
              Upload Document and Live Photo
            </h2>
            <UploadForm onResult={handleResult} onError={handleError} />
          </div>
        ) : screeningResult ? (
          <ResultsDashboard result={screeningResult} />
        ) : null}
      </main>

      {/* FOOTER */}
      <footer className="fixed bottom-0 w-full bg-white border-t py-3 text-center text-xs text-gray-500">
        SIH 2026 — Team AIGES — AI Document Screening System
      </footer>
    </div>
  );
}
