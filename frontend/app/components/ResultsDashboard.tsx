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
  Search,
  ChevronDown,
  ChevronUp,
  Fingerprint,
} from 'lucide-react';
import * as Progress from '@radix-ui/react-progress';

interface ResultsDashboardProps {
  result: ScreeningResult;
}

export default function ResultsDashboard({ result }: ResultsDashboardProps) {
  const [showRawText, setShowRawText] = useState(false);

  // Safe destructuring with fallbacks for null/undefined resilience
  const risk = result?.risk || {
    risk_score: 0,
    risk_band: 'unknown',
    reasons: [],
    contributions: {},
  };
  const classifier = result?.classifier || {
    doc_type: 'unknown',
    doc_type_confidence: 0,
    doc_bbox: null,
  };
  const ocr = result?.ocr || {
    fields: {},
    field_confidences: {},
    raw_text: '',
  };
  const mrz = result?.mrz || {
    mrz_present: false,
    mrz_fields: {},
    checksum_valid: false,
    cross_check: {},
  };
  const rules = result?.rules || {
    is_expired: false,
    format_valid: false,
    logic_valid: false,
    flags: [],
  };
  const tamper = result?.tamper || {
    suspicion_score: 0,
    flagged_regions: [],
    signals: {},
  };
  const face = result?.face || {
    similarity: 0,
    match_band: 'unknown',
    liveness_passed: null,
  };
  const db = result?.db || {
    status: 'unknown',
    record_meta: null,
  };

  const riskBand = (risk.risk_band || 'unknown').toLowerCase();
  const tamperSuspected = (tamper.suspicion_score || 0) >= 0.5;

  // Risk styling
  const getRiskColor = (band: string) => {
    switch (band) {
      case 'low':
        return 'text-green-800 bg-green-50 border-green-200';
      case 'medium':
        return 'text-yellow-800 bg-yellow-50 border-yellow-200';
      case 'high':
        return 'text-red-800 bg-red-50 border-red-200';
      default:
        return 'text-gray-800 bg-gray-50 border-gray-200';
    }
  };

  const getRiskProgressColor = (band: string) => {
    switch (band) {
      case 'low':
        return 'bg-green-500';
      case 'medium':
        return 'bg-yellow-500';
      case 'high':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getBadgeClass = (status: boolean | null | undefined) => {
    if (status === true) {
      return 'bg-green-100 text-green-800 border-green-200';
    }
    if (status === false) {
      return 'bg-red-100 text-red-800 border-red-200';
    }
    return 'bg-gray-100 text-gray-700 border-gray-200';
  };

  // Known OCR fields to render first with clean labels
  const standardOcrKeys: Record<string, string> = {
    doc_number: 'Document Number',
    name: 'Full Name',
    dob: 'Date of Birth',
    nationality: 'Nationality',
    expiry_date: 'Expiry Date',
    issue_date: 'Issue Date',
  };

  // Extract all OCR field entries
  const allOcrFields = ocr.fields || {};
  const ocrKeys = Array.from(
    new Set([...Object.keys(standardOcrKeys), ...Object.keys(allOcrFields)])
  );

  return (
    <div className="w-full max-w-6xl mx-auto p-4 md:p-6 space-y-6">
      {/* 1. OVERALL RISK HEADER */}
      <div className={`border-2 rounded-xl p-6 md:p-8 shadow-sm transition-all ${getRiskColor(riskBand)}`}>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <Shield className="w-8 h-8 text-current" />
              <h2 className="text-2xl md:text-3xl font-bold">
                Risk Score: {risk.risk_score ?? 0} / 100
              </h2>
            </div>
            <p className="text-base md:text-lg font-semibold uppercase tracking-wide">
              {risk.risk_band || 'UNKNOWN'} RISK
            </p>
          </div>
          <div className="text-right hidden md:block">
            <span className="text-xs font-mono text-gray-500 bg-white/70 px-2.5 py-1 rounded border">
              ID: {result.session_id ? `${result.session_id.slice(0, 8)}...` : 'N/A'}
            </span>
          </div>
        </div>

        {/* Radix Progress Bar */}
        <Progress.Root className="relative overflow-hidden bg-gray-200 rounded-full w-full h-4 mt-5">
          <Progress.Indicator
            className={`h-full transition-transform duration-500 ${getRiskProgressColor(riskBand)}`}
            style={{ transform: `translateX(-${Math.max(0, 100 - (risk.risk_score || 0))}%)` }}
          />
        </Progress.Root>

        {/* Risk Contributions breakdown */}
        {risk.contributions && Object.keys(risk.contributions).length > 0 && (
          <div className="mt-5 pt-4 border-t border-black/10">
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-600 mb-2">
              Risk Signal Contributions:
            </p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(risk.contributions).map(([signal, weight]) => (
                <span
                  key={signal}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-white/80 border border-black/10 text-gray-700"
                >
                  <span className="capitalize">{signal.replace(/_/g, ' ')}:</span>
                  <span className="font-semibold">{typeof weight === 'number' ? weight.toFixed(3) : String(weight)}</span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* TOP RISK REASONS (if any detected) */}
      {risk.reasons && risk.reasons.length > 0 && risk.reasons[0] !== 'No significant risk factors detected' ? (
        <div className="border border-red-200 rounded-xl p-5 bg-red-50/80 shadow-sm">
          <h3 className="text-md font-bold mb-3 flex items-center gap-2 text-red-800">
            <AlertTriangle className="w-5 h-5 text-red-600 shrink-0" />
            Identified Risk Factors ({risk.reasons.length})
          </h3>
          <ul className="space-y-2">
            {risk.reasons.map((reason, idx) => (
              <li key={idx} className="flex items-start gap-2.5 text-sm text-red-900">
                <XCircle className="w-4 h-4 text-red-600 mt-0.5 shrink-0" />
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="border border-green-200 rounded-xl p-4 bg-green-50/70 shadow-sm flex items-center gap-2.5 text-sm text-green-800">
          <CheckCircle className="w-5 h-5 text-green-600 shrink-0" />
          <span>No critical risk factors detected during automated screening.</span>
        </div>
      )}

      {/* 2. SUMMARY GRID — 4 PILLARS */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Module: Classifier */}
        <div className="border rounded-xl p-4 bg-white shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-gray-500 uppercase flex items-center gap-1.5">
                <FileText className="w-4 h-4 text-blue-600" />
                Classification
              </span>
              <span
                className={`text-xs px-2 py-0.5 rounded-full border font-medium ${
                  classifier.doc_type && classifier.doc_type !== 'unknown'
                    ? 'bg-blue-50 text-blue-700 border-blue-200'
                    : 'bg-gray-100 text-gray-600 border-gray-200'
                }`}
              >
                {classifier.doc_type || 'Unknown'}
              </span>
            </div>
            <p className="text-xl font-bold text-gray-900 capitalize">
              {classifier.doc_type || 'Unknown'}
            </p>
          </div>
          <div className="mt-3 text-xs text-gray-500">
            Confidence: <span className="font-semibold text-gray-700">{((classifier.doc_type_confidence || 0) * 100).toFixed(1)}%</span>
            {classifier.doc_bbox && (
              <span className="block mt-0.5 text-[11px] text-gray-400">
                BBox: [{classifier.doc_bbox.slice(0, 4).join(', ')}]
              </span>
            )}
          </div>
        </div>

        {/* Module: Face Verification */}
        <div className="border rounded-xl p-4 bg-white shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-gray-500 uppercase flex items-center gap-1.5">
                <UserCheck className="w-4 h-4 text-indigo-600" />
                Face Match
              </span>
              <span
                className={`text-xs px-2 py-0.5 rounded-full border font-medium ${
                  face.match_band === 'confident_match'
                    ? 'bg-green-50 text-green-700 border-green-200'
                    : face.match_band === 'review'
                    ? 'bg-yellow-50 text-yellow-700 border-yellow-200'
                    : 'bg-red-50 text-red-700 border-red-200'
                }`}
              >
                {(face.match_band || 'unknown').replace(/_/g, ' ')}
              </span>
            </div>
            <p className="text-xl font-bold text-gray-900">
              {((face.similarity || 0) * 100).toFixed(1)}%
            </p>
          </div>
          <div className="mt-3 text-xs text-gray-500">
            Liveness:{' '}
            <span className="font-semibold text-gray-700">
              {face.liveness_passed === true
                ? 'Passed'
                : face.liveness_passed === false
                ? 'Failed'
                : 'Not Evaluated'}
            </span>
          </div>
        </div>

        {/* Module: Tamper Detection */}
        <div className="border rounded-xl p-4 bg-white shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-gray-500 uppercase flex items-center gap-1.5">
                <Fingerprint className="w-4 h-4 text-purple-600" />
                Forensics
              </span>
              <span
                className={`text-xs px-2 py-0.5 rounded-full border font-medium ${
                  tamperSuspected
                    ? 'bg-red-50 text-red-700 border-red-200'
                    : 'bg-green-50 text-green-700 border-green-200'
                }`}
              >
                {tamperSuspected ? 'Suspected' : 'Clear'}
              </span>
            </div>
            <p className="text-xl font-bold text-gray-900">
              {((tamper.suspicion_score || 0) * 100).toFixed(1)}%
            </p>
          </div>
          <div className="mt-3 text-xs text-gray-500">
            Regions Flagged:{' '}
            <span className="font-semibold text-gray-700">
              {tamper.flagged_regions?.length || 0}
            </span>
          </div>
        </div>

        {/* Module: Database Check */}
        <div className="border rounded-xl p-4 bg-white shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-gray-500 uppercase flex items-center gap-1.5">
                <Database className="w-4 h-4 text-teal-600" />
                Watchlist / DB
              </span>
              <span
                className={`text-xs px-2 py-0.5 rounded-full border font-medium ${
                  db.status === 'clean' || db.status === 'not_found'
                    ? 'bg-green-50 text-green-700 border-green-200'
                    : 'bg-red-50 text-red-700 border-red-200'
                }`}
              >
                {(db.status || 'unknown').replace(/_/g, ' ')}
              </span>
            </div>
            <p className="text-xl font-bold text-gray-900 capitalize">
              {(db.status || 'not_found').replace(/_/g, ' ')}
            </p>
          </div>
          <div className="mt-3 text-xs text-gray-500">
            Meta Record:{' '}
            <span className="font-semibold text-gray-700">
              {db.record_meta ? 'Record Attached' : 'None'}
            </span>
          </div>
        </div>
      </div>

      {/* 3. OCR EXTRACTION & DOCUMENT OVERVIEW */}
      <div className="border rounded-xl p-6 bg-white shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b">
          <div className="flex items-center gap-2">
            <Scan className="w-5 h-5 text-blue-600" />
            <h3 className="text-lg font-bold text-gray-900">OCR Extracted Fields</h3>
          </div>
          <button
            type="button"
            onClick={() => setShowRawText(!showRawText)}
            className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-800 font-medium px-2.5 py-1 rounded-md border border-blue-200 hover:bg-blue-50 transition"
          >
            {showRawText ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            {showRawText ? 'Hide Raw OCR Text' : 'View Raw OCR Text'}
          </button>
        </div>

        {/* Fields Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
          {ocrKeys.map((key) => {
            const label = standardOcrKeys[key] || key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
            const value = allOcrFields[key];
            const confidence = ocr.field_confidences?.[key];
            const isExpiry = key === 'expiry_date';

            return (
              <div key={key} className="p-3.5 bg-gray-50/70 rounded-lg border border-gray-200 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold text-gray-500">{label}</span>
                    {typeof confidence === 'number' && (
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-medium ${
                          confidence >= 0.8
                            ? 'bg-green-100 text-green-700'
                            : confidence >= 0.5
                            ? 'bg-yellow-100 text-yellow-700'
                            : 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {(confidence * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                  <p
                    className={`font-semibold text-sm ${
                      isExpiry && rules.is_expired ? 'text-red-600' : 'text-gray-900'
                    }`}
                  >
                    {value ? value : <span className="text-gray-400 italic font-normal">Not detected</span>}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Collapsible Raw Text */}
        {showRawText && (
          <div className="mt-4 p-4 bg-gray-900 rounded-lg text-gray-100 text-xs font-mono overflow-x-auto whitespace-pre-wrap max-h-48 border border-gray-800">
            <p className="text-gray-400 mb-1 border-b border-gray-700 pb-1 uppercase tracking-wider text-[10px]">
              Raw OCR Buffer Output:
            </p>
            {ocr.raw_text ? ocr.raw_text : <span className="text-gray-500 italic">No text extracted</span>}
          </div>
        )}
      </div>

      {/* 4. MRZ & RULE VALIDATION SIDE-BY-SIDE */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* MRZ DETAILS */}
        <div className="border rounded-xl p-6 bg-white shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b">
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-indigo-600" />
              <h3 className="text-lg font-bold text-gray-900">MRZ Verification</h3>
            </div>
            <span
              className={`text-xs px-2.5 py-1 rounded-full border font-semibold ${
                mrz.mrz_present ? 'bg-green-50 text-green-700 border-green-200' : 'bg-gray-100 text-gray-600 border-gray-200'
              }`}
            >
              {mrz.mrz_present ? 'MRZ Detected' : 'No MRZ Detected'}
            </span>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border text-sm">
              <span className="font-medium text-gray-700">Checksum Validation</span>
              <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-semibold border ${getBadgeClass(mrz.mrz_present ? mrz.checksum_valid : null)}`}>
                {mrz.mrz_present ? (mrz.checksum_valid ? 'Valid Checksum' : 'Checksum Failed') : 'N/A'}
              </span>
            </div>

            {/* MRZ Cross-Check Items */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                Cross-Check with Visual OCR:
              </p>
              <div className="grid grid-cols-2 gap-2">
                {mrz.cross_check && Object.keys(mrz.cross_check).length > 0 ? (
                  Object.entries(mrz.cross_check).map(([key, match]) => (
                    <div
                      key={key}
                      className="p-2.5 rounded-lg border bg-gray-50/50 flex items-center justify-between text-xs"
                    >
                      <span className="capitalize text-gray-600">{key.replace(/_/g, ' ')}</span>
                      {match ? (
                        <CheckCircle className="w-4 h-4 text-green-600 shrink-0" />
                      ) : (
                        <XCircle className="w-4 h-4 text-red-500 shrink-0" />
                      )}
                    </div>
                  ))
                ) : (
                  <div className="col-span-2 text-xs text-gray-400 italic p-2 bg-gray-50 rounded border">
                    No cross-check data available
                  </div>
                )}
              </div>
            </div>

            {/* MRZ Parsed Fields */}
            {mrz.mrz_fields && Object.keys(mrz.mrz_fields).length > 0 && (
              <div className="pt-2">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  Parsed MRZ Fields:
                </p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {Object.entries(mrz.mrz_fields).map(([fieldKey, fieldVal]) => (
                    <div key={fieldKey} className="p-2 bg-gray-50 rounded border">
                      <span className="text-gray-500 block text-[11px] capitalize">{fieldKey.replace(/_/g, ' ')}</span>
                      <span className="font-semibold text-gray-800 truncate block">{fieldVal || '—'}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* RULE VALIDATION */}
        <div className="border rounded-xl p-6 bg-white shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-emerald-600" />
              <h3 className="text-lg font-bold text-gray-900">Rule Validation</h3>
            </div>
            <span
              className={`text-xs px-2.5 py-1 rounded-full border font-semibold ${
                !rules.is_expired && rules.format_valid && rules.logic_valid
                  ? 'bg-green-50 text-green-700 border-green-200'
                  : 'bg-amber-50 text-amber-700 border-amber-200'
              }`}
            >
              {!rules.is_expired && rules.format_valid && rules.logic_valid ? 'Rules Passed' : 'Flagged by Rules'}
            </span>
          </div>

          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-2">
              <div className="p-3 bg-gray-50 rounded-lg border text-center">
                <p className="text-[11px] text-gray-500 mb-1">Format Valid</p>
                <span className={`inline-flex px-2 py-0.5 rounded text-xs font-semibold border ${getBadgeClass(rules.format_valid)}`}>
                  {rules.format_valid ? 'Valid' : 'Invalid'}
                </span>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg border text-center">
                <p className="text-[11px] text-gray-500 mb-1">Logic Valid</p>
                <span className={`inline-flex px-2 py-0.5 rounded text-xs font-semibold border ${getBadgeClass(rules.logic_valid)}`}>
                  {rules.logic_valid ? 'Valid' : 'Invalid'}
                </span>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg border text-center">
                <p className="text-[11px] text-gray-500 mb-1">Expiry Status</p>
                <span className={`inline-flex px-2 py-0.5 rounded text-xs font-semibold border ${getBadgeClass(!rules.is_expired)}`}>
                  {rules.is_expired ? 'Expired' : 'Active'}
                </span>
              </div>
            </div>

            {/* Rule Flags */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                Rule Checks & Observations:
              </p>
              {rules.flags && rules.flags.length > 0 ? (
                <ul className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                  {rules.flags.map((flag, idx) => (
                    <li key={idx} className="flex items-start gap-2 p-2 bg-amber-50/60 border border-amber-200 rounded text-xs text-amber-900">
                      <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
                      <span>{flag}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="p-3 bg-green-50/60 border border-green-200 rounded-lg text-xs text-green-800 flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-green-600 shrink-0" />
                  <span>All deterministic document rules satisfied without any flags.</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 5. FORENSICS & DATABASE DETAILS SIDE-BY-SIDE */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* TAMPER / FORENSICS SIGNALS */}
        <div className="border rounded-xl p-6 bg-white shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b">
            <div className="flex items-center gap-2">
              <Fingerprint className="w-5 h-5 text-purple-600" />
              <h3 className="text-lg font-bold text-gray-900">Forensics & Tampering</h3>
            </div>
            <span
              className={`text-xs px-2.5 py-1 rounded-full border font-semibold ${
                tamperSuspected ? 'bg-red-50 text-red-700 border-red-200' : 'bg-green-50 text-green-700 border-green-200'
              }`}
            >
              Suspicion Score: {((tamper.suspicion_score || 0) * 100).toFixed(2)}%
            </span>
          </div>

          <div className="space-y-3">
            {/* Forensic Signals */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                Forensic Signal Analysis:
              </p>
              <div className="grid grid-cols-3 gap-2 text-center text-xs">
                <div className="p-2.5 bg-gray-50 rounded border">
                  <p className="text-gray-500 text-[11px]">ELA Score</p>
                  <p className="font-semibold text-gray-800 mt-0.5">
                    {typeof tamper.signals?.ela_score === 'number'
                      ? (tamper.signals.ela_score * 100).toFixed(1) + '%'
                      : '0.0%'}
                  </p>
                </div>
                <div className="p-2.5 bg-gray-50 rounded border">
                  <p className="text-gray-500 text-[11px]">Copy-Move</p>
                  <p className="font-semibold text-gray-800 mt-0.5">
                    {typeof tamper.signals?.copy_move_score === 'number'
                      ? (tamper.signals.copy_move_score * 100).toFixed(1) + '%'
                      : '0.0%'}
                  </p>
                </div>
                <div className="p-2.5 bg-gray-50 rounded border">
                  <p className="text-gray-500 text-[11px]">Font Inconsistency</p>
                  <p className="font-semibold text-gray-800 mt-0.5">
                    {typeof tamper.signals?.font_inconsistency_score === 'number'
                      ? (tamper.signals.font_inconsistency_score * 100).toFixed(1) + '%'
                      : '0.0%'}
                  </p>
                </div>
              </div>
            </div>

            {/* Flagged Regions */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                Flagged Region Bounding Boxes ({tamper.flagged_regions?.length || 0}):
              </p>
              {tamper.flagged_regions && tamper.flagged_regions.length > 0 ? (
                <div className="p-2.5 bg-gray-50 rounded border text-[11px] font-mono text-gray-600 max-h-24 overflow-y-auto">
                  {tamper.flagged_regions.slice(0, 10).map((box, idx) => (
                    <div key={idx}>
                      Region {idx + 1}: [{box.join(', ')}]
                    </div>
                  ))}
                  {tamper.flagged_regions.length > 10 && (
                    <div className="text-gray-400 italic">
                      + {tamper.flagged_regions.length - 10} more regions detected
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-2.5 bg-green-50/60 border border-green-200 rounded text-xs text-green-800 flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-green-600 shrink-0" />
                  <span>No suspicious tampering regions flagged on this document.</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* DATABASE / WATCHLIST AUDIT */}
        <div className="border rounded-xl p-6 bg-white shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b">
            <div className="flex items-center gap-2">
              <Database className="w-5 h-5 text-teal-600" />
              <h3 className="text-lg font-bold text-gray-900">Database & Watchlist Audit</h3>
            </div>
            <span
              className={`text-xs px-2.5 py-1 rounded-full border font-semibold ${
                db.status === 'clean' || db.status === 'not_found'
                  ? 'bg-green-50 text-green-700 border-green-200'
                  : 'bg-red-50 text-red-700 border-red-200'
              }`}
            >
              Status: {(db.status || 'unknown').replace(/_/g, ' ')}
            </span>
          </div>

          <div className="space-y-3">
            <div className="p-3 bg-gray-50 rounded-lg border text-sm flex items-center justify-between">
              <span className="font-medium text-gray-700">Immigration Watchlist Status</span>
              <span className="font-semibold capitalize text-gray-900">
                {(db.status || 'not_found').replace(/_/g, ' ')}
              </span>
            </div>

            {/* Record Metadata Display (safe without exposing sensitive internals) */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                Sanctions & Database Metadata:
              </p>
              {db.record_meta && Object.keys(db.record_meta).length > 0 ? (
                <div className="p-3 bg-gray-50 rounded-lg border space-y-1 text-xs">
                  {Object.entries(db.record_meta).map(([metaKey, metaVal]) => (
                    <div key={metaKey} className="flex justify-between border-b border-gray-200/60 pb-1">
                      <span className="font-medium text-gray-600 capitalize">{metaKey.replace(/_/g, ' ')}:</span>
                      <span className="text-gray-900 font-mono">
                        {typeof metaVal === 'object' ? JSON.stringify(metaVal) : String(metaVal)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-3 bg-gray-50 rounded-lg border text-xs text-gray-600 flex items-center gap-2">
                  <Search className="w-4 h-4 text-gray-400 shrink-0" />
                  <span>No watchlist or criminal database records returned for this subject.</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 6. SESSION AUDIT FOOTER */}
      <div className="p-4 bg-gray-100/70 border border-gray-200 rounded-xl text-center text-xs text-gray-500 font-mono">
        Audit Session ID: <span className="font-semibold text-gray-700">{result.session_id || 'N/A'}</span>
      </div>
    </div>
  );
}
