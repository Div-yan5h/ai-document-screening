'use client';

import { ScreeningResult } from '@/app/types/contracts';
import { CheckCircle, XCircle, AlertTriangle, Shield } from 'lucide-react';
import * as Progress from '@radix-ui/react-progress';

interface ResultsDashboardProps {
  result: ScreeningResult;
}

export default function ResultsDashboard({ result }: ResultsDashboardProps) {
  const { risk, classifier, ocr, mrz, rules, face, db } = result;

  // Risk color mapping
  const getRiskColor = (band: string) => {
    switch (band) {
      case 'low': return 'text-green-600 bg-green-50 border-green-200';
      case 'medium': return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'high': return 'text-red-600 bg-red-50 border-red-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getRiskProgressColor = (band: string) => {
    switch (band) {
      case 'low': return 'bg-green-500';
      case 'medium': return 'bg-yellow-500';
      case 'high': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  return (
    <div className="w-full max-w-6xl mx-auto p-6 space-y-6">
      {/* RISK SCORE HEADER */}
      <div className={`border-2 rounded-lg p-8 ${getRiskColor(risk.risk_band)}`}>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold mb-2">Risk Score: {risk.risk_score}/100</h2>
            <p className="text-lg font-semibold uppercase">{risk.risk_band} Risk</p>
          </div>
          <Shield className="w-24 h-24 opacity-20" />
        </div>
        <Progress.Root className="relative overflow-hidden bg-gray-200 rounded-full w-full h-4 mt-4">
          <Progress.Indicator
            className={`h-full transition-transform duration-500 ${getRiskProgressColor(risk.risk_band)}`}
            style={{ transform: `translateX(-${100 - risk.risk_score}%)` }}
          />
        </Progress.Root>
      </div>

      {/* TOP REASONS */}
      {risk.reasons.length > 0 && risk.reasons[0] !== "No significant risk factors detected" && (
        <div className="border rounded-lg p-6 bg-red-50">
          <h3 className="text-lg font-bold mb-3 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-red-600" />
            Risk Factors Detected
          </h3>
          <ul className="space-y-2">
            {risk.reasons.map((reason, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm">
                <XCircle className="w-4 h-4 text-red-600 mt-0.5 flex-shrink-0" />
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* DOCUMENT OVERVIEW */}
      <div className="border rounded-lg p-6 bg-white">
        <h3 className="text-lg font-bold mb-4">Document Overview</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-gray-500">Document Type</p>
            <p className="font-semibold">{classifier.doc_type} ({(classifier.doc_type_confidence * 100).toFixed(0)}%)</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Document Number</p>
            <p className="font-semibold">{ocr.fields.doc_number || 'N/A'}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Name</p>
            <p className="font-semibold">{ocr.fields.name || 'N/A'}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Date of Birth</p>
            <p className="font-semibold">{ocr.fields.dob || 'N/A'}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Nationality</p>
            <p className="font-semibold">{ocr.fields.nationality || 'N/A'}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Expiry Date</p>
            <p className={`font-semibold ${rules.is_expired ? 'text-red-600' : ''}`}>
              {ocr.fields.expiry_date || 'N/A'}
            </p>
          </div>
        </div>
      </div>

      {/* VERIFICATION STATUS GRID */}
      <div className="grid grid-cols-2 gap-4">
        {/* MRZ Check */}
        <div className="border rounded-lg p-4 bg-white">
          <h4 className="font-semibold mb-2 flex items-center gap-2">
            {mrz.mrz_present && mrz.checksum_valid && Object.values(mrz.cross_check).every(v => v) ? (
              <CheckCircle className="w-5 h-5 text-green-600" />
            ) : (
              <XCircle className="w-5 h-5 text-red-600" />
            )}
            MRZ Verification
          </h4>
          <p className="text-sm text-gray-600">
            {mrz.mrz_present ? `Checksum: ${mrz.checksum_valid ? 'Valid' : 'Invalid'}` : 'No MRZ found'}
          </p>
        </div>

        {/* Rule Validation */}
        <div className="border rounded-lg p-4 bg-white">
          <h4 className="font-semibold mb-2 flex items-center gap-2">
            {!rules.is_expired && rules.format_valid && rules.logic_valid ? (
              <CheckCircle className="w-5 h-5 text-green-600" />
            ) : (
              <XCircle className="w-5 h-5 text-red-600" />
            )}
            Rule Validation
          </h4>
          <p className="text-sm text-gray-600">
            {rules.is_expired ? 'Expired' : 'Valid'}
          </p>
        </div>

        {/* Face Match */}
        <div className="border rounded-lg p-4 bg-white">
          <h4 className="font-semibold mb-2 flex items-center gap-2">
            {face.match_band === 'confident_match' ? (
              <CheckCircle className="w-5 h-5 text-green-600" />
            ) : face.match_band === 'review' ? (
              <AlertTriangle className="w-5 h-5 text-yellow-600" />
            ) : (
              <XCircle className="w-5 h-5 text-red-600" />
            )}
            Face Verification
          </h4>
          <p className="text-sm text-gray-600">
            {(face.similarity * 100).toFixed(0)}% match ({face.match_band.replace('_', ' ')})
          </p>
        </div>

        {/* Database Status */}
        <div className="border rounded-lg p-4 bg-white">
          <h4 className="font-semibold mb-2 flex items-center gap-2">
            {db.status === 'clean' || db.status === 'not_found' ? (
              <CheckCircle className="w-5 h-5 text-green-600" />
            ) : (
              <XCircle className="w-5 h-5 text-red-600" />
            )}
            Database Check
          </h4>
          <p className="text-sm text-gray-600 capitalize">
            {db.status.replace('_', ' ')}
          </p>
        </div>
      </div>

      {/* SESSION ID */}
      <div className="text-center text-xs text-gray-400">
        Session ID: {result.session_id}
      </div>
    </div>
  );
}
