'use client';

import React, { useState } from 'react';
import { ScreeningResult } from '@/app/types/contracts';
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Shield,
  FileText,
  Scan,
  UserCheck,
  Database,
  ChevronDown,
  ChevronUp,
  Fingerprint,
  Scale,
  Check,
  Ban,
  Clock
} from 'lucide-react';
import * as Progress from '@radix-ui/react-progress';

interface ResultsDashboardProps {
  result: ScreeningResult;
}

export default function ResultsDashboard({ result }: ResultsDashboardProps) {
  const [showRawText, setShowRawText] = useState(false);

  // Safe destructuring
  const risk = result?.risk || { risk_score: 0, risk_band: 'unknown', reasons: [], contributions: {} };
  const classifier = result?.classifier || { doc_type: 'unknown', doc_type_confidence: 0, doc_bbox: null };
  const ocr = result?.ocr || { fields: {}, field_confidences: {}, raw_text: '' };
  const mrz = result?.mrz || { mrz_present: false, mrz_fields: {}, checksum_valid: false, cross_check: {} };
  const rules = result?.rules || { is_expired: false, format_valid: false, logic_valid: false, flags: [] };
  const tamper = result?.tamper || { suspicion_score: 0, flagged_regions: [], signals: {} };
  const face = result?.face || { similarity: 0, match_band: 'unknown', liveness_passed: null };
  const db = result?.db || { status: 'unknown', record_meta: null };

  const riskBand = (risk.risk_band || 'unknown').toLowerCase();
  const tamperSuspected = (tamper.suspicion_score || 0) >= 0.5;

  // Professional Workstation Colors
  const getRiskColor = (band: string) => {
    switch (band) {
      case 'low': return 'text-emerald-400 bg-emerald-950/20 border-emerald-900/50';
      case 'medium': return 'text-amber-400 bg-amber-950/20 border-amber-900/50';
      case 'high': return 'text-red-400 bg-red-950/20 border-red-900/50';
      default: return 'text-slate-400 bg-slate-900 border-slate-800';
    }
  };

  const getRiskProgressColor = (band: string) => {
    switch (band) {
      case 'low': return 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.3)]';
      case 'medium': return 'bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.3)]';
      case 'high': return 'bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.3)]';
      default: return 'bg-slate-500';
    }
  };

  const getStatusBadge = (status: boolean | null | undefined, passText = 'PASS', failText = 'FAIL') => {
    if (status === true) {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-emerald-950/50 text-emerald-400 border border-emerald-800/50">
          <CheckCircle className="w-3 h-3" /> {passText}
        </span>
      );
    }
    if (status === false) {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-red-950/50 text-red-400 border border-red-800/50">
          <XCircle className="w-3 h-3" /> {failText}
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
        N/A
      </span>
    );
  };

  // Known OCR fields
  const standardOcrKeys: Record<string, string> = {
    doc_number: 'Document Number',
    name: 'Full Name',
    dob: 'Date of Birth',
    nationality: 'Nationality',
    expiry_date: 'Expiry Date',
    issue_date: 'Issue Date',
  };

  const allOcrFields = ocr.fields || {};
  const ocrKeys = Array.from(new Set([...Object.keys(standardOcrKeys), ...Object.keys(allOcrFields)]));

  return (
    <div className="w-full mx-auto space-y-6">
      
      {/* 1. OFFICER ACTION BAR */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-4 bg-slate-900 border border-slate-800 rounded-xl shadow-lg">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-sm font-mono text-slate-300">SESSION: {result.session_id || 'N/A'}</span>
        </div>
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <button className="flex-1 sm:flex-none flex items-center justify-center gap-2 px-4 py-2 bg-emerald-600/10 hover:bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-sm font-bold tracking-wide transition-colors">
            <Check className="w-4 h-4" /> APPROVE
          </button>
          <button className="flex-1 sm:flex-none flex items-center justify-center gap-2 px-4 py-2 bg-amber-600/10 hover:bg-amber-600/20 text-amber-400 border border-amber-500/30 rounded-lg text-sm font-bold tracking-wide transition-colors">
            <Clock className="w-4 h-4" /> ESCALATE
          </button>
          <button className="flex-1 sm:flex-none flex items-center justify-center gap-2 px-4 py-2 bg-red-600/10 hover:bg-red-600/20 text-red-400 border border-red-500/30 rounded-lg text-sm font-bold tracking-wide transition-colors">
            <Ban className="w-4 h-4" /> DENY
          </button>
        </div>
      </div>

      {/* 2. OVERALL RISK SUMMARY */}
      <div className={`relative overflow-hidden border rounded-xl p-6 sm:p-8 shadow-xl ${getRiskColor(riskBand)}`}>
        {/* Subtle background glow effect based on risk */}
        <div className="absolute -right-20 -top-20 w-64 h-64 bg-current opacity-[0.03] rounded-full blur-3xl pointer-events-none" />
        
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 relative z-10">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <Shield className="w-6 h-6 opacity-80" />
              <h2 className="text-sm font-bold tracking-widest uppercase opacity-80">Risk Assessment</h2>
            </div>
            <div className="flex items-baseline gap-4 mt-2">
              <span className="text-6xl md:text-7xl font-bold tracking-tighter">
                {risk.risk_score ?? 0}
              </span>
              <span className="text-xl md:text-2xl font-semibold uppercase tracking-widest opacity-90">
                {risk.risk_band || 'UNKNOWN'}
              </span>
            </div>
          </div>

          <div className="w-full md:w-1/2 max-w-md space-y-4">
            <div>
              <div className="flex justify-between text-xs font-mono mb-1.5 opacity-70">
                <span>0</span>
                <span>100</span>
              </div>
              <Progress.Root className="relative overflow-hidden bg-black/20 rounded-full w-full h-3 border border-white/5">
                <Progress.Indicator
                  className={`h-full transition-transform duration-1000 ease-out ${getRiskProgressColor(riskBand)}`}
                  style={{ transform: `translateX(-${Math.max(0, 100 - (risk.risk_score || 0))}%)` }}
                />
              </Progress.Root>
            </div>
            
            {/* Risk Contributions breakdown */}
            {risk.contributions && Object.keys(risk.contributions).length > 0 && (
              <div className="pt-2">
                <p className="text-[10px] font-bold uppercase tracking-widest opacity-60 mb-2">
                  Signal Contributions
                </p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(risk.contributions).filter((entry) => (entry[1] as number) > 0).map(([signal, weight]) => (
                    <div key={signal} className="flex items-center gap-1.5 px-2 py-1 rounded bg-black/10 border border-white/10 text-[11px] font-mono">
                      <span className="opacity-80">{signal.replace(/_/g, ' ')}:</span>
                      <span className="font-bold">+{typeof weight === 'number' ? weight.toFixed(3) : String(weight)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* TOP RISK REASONS */}
        {risk.reasons && risk.reasons.length > 0 && risk.reasons[0] !== 'No significant risk factors detected' && (
          <div className="mt-6 pt-5 border-t border-current/20 relative z-10">
            <h3 className="text-xs font-bold uppercase tracking-widest flex items-center gap-2 mb-3 opacity-80">
              <AlertTriangle className="w-4 h-4" /> Flagged Reasons
            </h3>
            <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {risk.reasons.map((reason, idx) => (
                <li key={idx} className="flex items-start gap-2.5 text-sm bg-black/10 px-3 py-2 rounded-lg border border-white/5">
                  <XCircle className="w-4 h-4 mt-0.5 shrink-0 opacity-80" />
                  <span className="opacity-90 leading-snug">{reason}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* 3. 5-PILLAR STATUS GRID */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Classification */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 text-blue-400 mb-3">
              <FileText className="w-5 h-5" />
              <h3 className="text-xs font-bold uppercase tracking-widest">Type</h3>
            </div>
            <p className="text-lg font-semibold text-slate-100 capitalize">
              {(classifier.doc_type || 'Unknown').replace(/_/g, ' ')}
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-800 flex justify-between items-end">
            <span className="text-[10px] text-slate-500 font-mono uppercase">Confidence</span>
            <span className="text-sm font-mono text-slate-300">{((classifier.doc_type_confidence || 0) * 100).toFixed(1)}%</span>
          </div>
        </div>

        {/* MRZ & Rules */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 text-indigo-400 mb-3">
              <Scale className="w-5 h-5" />
              <h3 className="text-xs font-bold uppercase tracking-widest">Rules</h3>
            </div>
            <div className="flex flex-col gap-2">
              <div className="flex justify-between items-center">
                <span className="text-xs text-slate-400">Format Valid</span>
                {getStatusBadge(rules.format_valid)}
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-slate-400">Logic Valid</span>
                {getStatusBadge(rules.logic_valid)}
              </div>
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-800 flex justify-between items-end">
            <span className="text-[10px] text-slate-500 font-mono uppercase">Flags</span>
            <span className={`text-sm font-mono ${rules.flags?.length ? 'text-amber-400' : 'text-emerald-400'}`}>
              {rules.flags?.length || 0}
            </span>
          </div>
        </div>

        {/* Tamper */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 text-purple-400 mb-3">
              <Fingerprint className="w-5 h-5" />
              <h3 className="text-xs font-bold uppercase tracking-widest">Tamper</h3>
            </div>
            <p className={`text-lg font-semibold ${tamperSuspected ? 'text-red-400' : 'text-emerald-400'}`}>
              {tamperSuspected ? 'Suspected' : 'Clear'}
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-800 flex justify-between items-end">
            <span className="text-[10px] text-slate-500 font-mono uppercase">Suspicion</span>
            <span className="text-sm font-mono text-slate-300">{((tamper.suspicion_score || 0) * 100).toFixed(1)}%</span>
          </div>
        </div>

        {/* Face */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 text-cyan-400 mb-3">
              <UserCheck className="w-5 h-5" />
              <h3 className="text-xs font-bold uppercase tracking-widest">Face Match</h3>
            </div>
            <p className={`text-lg font-semibold capitalize ${
              face.match_band === 'confident_match' ? 'text-emerald-400' : 
              face.match_band === 'review' ? 'text-amber-400' : 'text-red-400'
            }`}>
              {(face.match_band || 'unknown').replace(/_/g, ' ')}
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-800 flex justify-between items-end">
            <span className="text-[10px] text-slate-500 font-mono uppercase">Similarity</span>
            <span className="text-sm font-mono text-slate-300">{((face.similarity || 0) * 100).toFixed(1)}%</span>
          </div>
        </div>

        {/* Database */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 text-teal-400 mb-3">
              <Database className="w-5 h-5" />
              <h3 className="text-xs font-bold uppercase tracking-widest">Database</h3>
            </div>
            <p className={`text-lg font-semibold capitalize ${
              db.status === 'clean' || db.status === 'not_found' ? 'text-emerald-400' : 'text-red-400'
            }`}>
              {(db.status || 'not_found').replace(/_/g, ' ')}
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-800 flex justify-between items-end">
            <span className="text-[10px] text-slate-500 font-mono uppercase">Meta</span>
            <span className="text-xs font-mono text-slate-400">{db.record_meta ? 'Attached' : 'None'}</span>
          </div>
        </div>
      </div>

      {/* 4. DETAILS SECTIONS */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* OCR EXTRACTION */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm space-y-5">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-sm font-bold uppercase tracking-widest text-slate-200 flex items-center gap-2">
              <Scan className="w-4 h-4 text-blue-500" /> OCR Data
            </h3>
            <button
              onClick={() => setShowRawText(!showRawText)}
              className="text-xs font-mono text-blue-400 hover:text-blue-300 flex items-center gap-1"
            >
              {showRawText ? 'HIDE RAW' : 'SHOW RAW'} {showRawText ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {ocrKeys.map((key) => {
              const label = standardOcrKeys[key] || key.replace(/_/g, ' ');
              const value = allOcrFields[key];
              const confidence = ocr.field_confidences?.[key];
              const isLowConf = typeof confidence === 'number' && confidence < 0.7;

              return (
                <div key={key} className="bg-slate-950 border border-slate-800 rounded-lg p-3">
                  <div className="flex justify-between items-center mb-1.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{label}</span>
                    {typeof confidence === 'number' && (
                      <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                        isLowConf ? 'bg-amber-950/50 text-amber-500 border border-amber-900/50' : 'text-slate-500'
                      }`}>
                        {(confidence * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                  <p className={`font-mono text-sm truncate ${isLowConf ? 'text-amber-200' : 'text-slate-200'} ${!value && 'italic opacity-50'}`}>
                    {value || 'Not Detected'}
                  </p>
                </div>
              );
            })}
          </div>

          {showRawText && (
            <div className="mt-4 p-4 bg-black/50 border border-slate-800 rounded-lg">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">Raw Buffer</p>
              <pre className="text-xs font-mono text-slate-400 whitespace-pre-wrap overflow-x-auto max-h-48 custom-scrollbar">
                {ocr.raw_text || 'No text extracted'}
              </pre>
            </div>
          )}
        </div>

        {/* MRZ & FORENSICS (Stacked) */}
        <div className="space-y-6">
          
          {/* FORENSICS METERS */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-widest text-slate-200 flex items-center gap-2 border-b border-slate-800 pb-3">
              <Fingerprint className="w-4 h-4 text-purple-500" /> Forensic Analysis
            </h3>
            
            <div className="space-y-3">
              {[
                { label: 'Error Level Analysis (ELA)', val: tamper.signals?.ela_score || 0 },
                { label: 'Copy-Move Detection', val: tamper.signals?.copy_move_score || 0 },
                { label: 'Font Inconsistency', val: tamper.signals?.font_inconsistency_score || 0 }
              ].map(sig => (
                <div key={sig.label}>
                  <div className="flex justify-between text-[11px] font-mono text-slate-400 mb-1">
                    <span>{sig.label}</span>
                    <span>{(sig.val * 100).toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-slate-950 h-1.5 rounded-full overflow-hidden border border-slate-800">
                    <div 
                      className={`h-full ${sig.val > 0.5 ? 'bg-red-500' : sig.val > 0.2 ? 'bg-amber-500' : 'bg-purple-500'}`}
                      style={{ width: `${Math.max(2, sig.val * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
              
              <div className="mt-4 pt-4 border-t border-slate-800 flex justify-between items-center">
                <span className="text-xs text-slate-400 font-medium">Flagged Regions Detected</span>
                <span className="px-2.5 py-1 bg-slate-950 border border-slate-800 rounded text-xs font-mono text-slate-300">
                  {tamper.flagged_regions?.length || 0}
                </span>
              </div>
            </div>
          </div>

          {/* MRZ DATA */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm space-y-4">
            <div className="flex justify-between items-center border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold uppercase tracking-widest text-slate-200 flex items-center gap-2">
                <FileText className="w-4 h-4 text-indigo-500" /> MRZ Validation
              </h3>
              {getStatusBadge(mrz.mrz_present, 'DETECTED', 'NOT DETECTED')}
            </div>

            {mrz.mrz_present ? (
              <div className="space-y-4">
                <div className="flex justify-between items-center p-3 bg-slate-950 border border-slate-800 rounded-lg">
                  <span className="text-xs text-slate-400 font-medium">Global Checksum</span>
                  {getStatusBadge(mrz.checksum_valid)}
                </div>
                
                {mrz.cross_check && Object.keys(mrz.cross_check).length > 0 && (
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">Visual Cross-Check</p>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(mrz.cross_check).map(([key, match]) => (
                        <div key={key} className="flex justify-between items-center p-2 bg-slate-950 border border-slate-800 rounded text-xs">
                          <span className="text-slate-400 capitalize">{key.replace(/_/g, ' ')}</span>
                          {match ? <CheckCircle className="w-3.5 h-3.5 text-emerald-500" /> : <XCircle className="w-3.5 h-3.5 text-red-500" />}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-center py-6 text-slate-500 text-sm font-mono italic">
                Document does not contain a Machine Readable Zone
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
