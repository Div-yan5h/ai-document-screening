'use client';

import React, { useState, ChangeEvent, useEffect } from 'react';
import { Upload, CheckCircle, XCircle, FileImage, Camera, Loader2, ServerCog } from 'lucide-react';
import { ScreeningResult } from '@/app/types/contracts';

export interface UploadFormProps {
  onResult: (result: ScreeningResult) => void;
  onError: (error: string) => void;
}

const PROGRESS_STAGES = [
  'INGESTING',
  'CLASSIFYING',
  'EXTRACTING',
  'VERIFYING',
  'RISK ASSESSMENT'
];

export default function UploadForm({ onResult, onError }: UploadFormProps) {
  const [docFile, setDocFile] = useState<File | null>(null);
  const [livePhoto, setLivePhoto] = useState<File | null>(null);
  const [docPreview, setDocPreview] = useState<string | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [progressStageIdx, setProgressStageIdx] = useState<number>(0);

  const handleDocChange = (file: File | null) => {
    if (!file) {
      setDocFile(null);
      setDocPreview(null);
      return;
    }
    setDocFile(file);
    const reader = new FileReader();
    reader.onloadend = () => {
      setDocPreview(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handlePhotoChange = (file: File | null) => {
    if (!file) {
      setLivePhoto(null);
      setPhotoPreview(null);
      return;
    }
    setLivePhoto(file);
    const reader = new FileReader();
    reader.onloadend = () => {
      setPhotoPreview(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  // Simulate progress steps if uploading
  useEffect(() => {
    if (!isUploading) {
      setProgressStageIdx(0);
      return;
    }
    const interval = setInterval(() => {
      setProgressStageIdx((prev) => Math.min(prev + 1, PROGRESS_STAGES.length - 1));
    }, 600); // Progress every 600ms while waiting for backend
    return () => clearInterval(interval);
  }, [isUploading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!docFile || !livePhoto || isUploading) return;

    setIsUploading(true);
    setProgressStageIdx(0);

    try {
      const formData = new FormData();
      formData.append('doc_file', docFile);
      formData.append('live_photo', livePhoto);

      const apiUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

      const response = await fetch(`${apiUrl}/screen`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        let errorDetail = `Server error (${response.status})`;
        try {
          const errData = await response.json();
          if (errData && errData.detail) {
            errorDetail =
              typeof errData.detail === 'string'
                ? errData.detail
                : JSON.stringify(errData.detail);
          }
        } catch {
          // fallback
        }
        throw new Error(errorDetail);
      }

      const result: ScreeningResult = await response.json();
      setProgressStageIdx(PROGRESS_STAGES.length - 1);
      setTimeout(() => {
        onResult(result);
      }, 300); // Short delay to let the user see the final stage
    } catch (err: unknown) {
      let errorMessage = 'An error occurred during document screening. Please check backend connection.';
      if (err instanceof Error) {
        errorMessage = err.message;
      }
      onError(errorMessage);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-4xl mx-auto space-y-8">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        
        {/* Document Upload Zone */}
        <div className="flex flex-col space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-sm font-bold text-slate-200 tracking-wide uppercase flex items-center gap-2">
              <FileImage className="w-4 h-4 text-slate-400" />
              Identity Document <span className="text-red-500">*</span>
            </label>
          </div>
          <div
            className={`relative border-2 border-dashed rounded-xl p-6 flex flex-col items-center justify-center transition-all min-h-[260px] group ${
              docPreview
                ? 'border-emerald-500/50 bg-emerald-950/20'
                : 'border-slate-700 bg-slate-800/50 hover:bg-slate-800 hover:border-blue-500/50'
            }`}
          >
            {docPreview ? (
              <div className="flex flex-col items-center space-y-4 w-full h-full justify-between">
                <div className="relative w-full h-40 rounded-lg overflow-hidden border border-emerald-500/30 bg-black/40 flex items-center justify-center p-1">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={docPreview}
                    alt="Document preview"
                    className="max-h-full max-w-full object-contain rounded-md"
                  />
                </div>
                <div className="flex items-center justify-between w-full px-1 text-sm">
                  <span className="flex items-center gap-2 font-medium text-emerald-400 truncate max-w-[200px]">
                    <CheckCircle className="w-4 h-4 shrink-0" />
                    {docFile?.name}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleDocChange(null)}
                    disabled={isUploading}
                    className="text-slate-400 hover:text-red-400 flex items-center gap-1 transition-colors disabled:opacity-50"
                  >
                    <XCircle className="w-4 h-4" /> <span className="text-xs font-semibold">REMOVE</span>
                  </button>
                </div>
              </div>
            ) : (
              <label className="flex flex-col items-center justify-center cursor-pointer w-full h-full p-4">
                <div className="w-14 h-14 rounded-full bg-slate-900 border border-slate-700 flex items-center justify-center mb-4 group-hover:scale-105 transition-transform group-hover:border-blue-500/50">
                  <Upload className="w-6 h-6 text-slate-400 group-hover:text-blue-400 transition-colors" />
                </div>
                <span className="text-sm font-semibold text-slate-300 text-center">
                  Drag and drop or click to browse
                </span>
                <span className="text-xs text-slate-500 mt-2 font-mono">
                  ACCEPTED: JPEG, JPG, PNG
                </span>
                <input
                  type="file"
                  accept="image/jpeg, image/png, image/jpg"
                  className="hidden"
                  onChange={(e: ChangeEvent<HTMLInputElement>) => {
                    const file = e.target.files?.[0] || null;
                    handleDocChange(file);
                  }}
                />
              </label>
            )}
          </div>
        </div>

        {/* Live Photo Upload Zone */}
        <div className="flex flex-col space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-sm font-bold text-slate-200 tracking-wide uppercase flex items-center gap-2">
              <Camera className="w-4 h-4 text-slate-400" />
              Live Subject Photo <span className="text-red-500">*</span>
            </label>
          </div>
          <div
            className={`relative border-2 border-dashed rounded-xl p-6 flex flex-col items-center justify-center transition-all min-h-[260px] group ${
              photoPreview
                ? 'border-emerald-500/50 bg-emerald-950/20'
                : 'border-slate-700 bg-slate-800/50 hover:bg-slate-800 hover:border-blue-500/50'
            }`}
          >
            {photoPreview ? (
              <div className="flex flex-col items-center space-y-4 w-full h-full justify-between">
                <div className="relative w-full h-40 rounded-lg overflow-hidden border border-emerald-500/30 bg-black/40 flex items-center justify-center p-1">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={photoPreview}
                    alt="Live photo preview"
                    className="max-h-full max-w-full object-contain rounded-md"
                  />
                </div>
                <div className="flex items-center justify-between w-full px-1 text-sm">
                  <span className="flex items-center gap-2 font-medium text-emerald-400 truncate max-w-[200px]">
                    <CheckCircle className="w-4 h-4 shrink-0" />
                    {livePhoto?.name}
                  </span>
                  <button
                    type="button"
                    onClick={() => handlePhotoChange(null)}
                    disabled={isUploading}
                    className="text-slate-400 hover:text-red-400 flex items-center gap-1 transition-colors disabled:opacity-50"
                  >
                    <XCircle className="w-4 h-4" /> <span className="text-xs font-semibold">REMOVE</span>
                  </button>
                </div>
              </div>
            ) : (
              <label className="flex flex-col items-center justify-center cursor-pointer w-full h-full p-4">
                <div className="w-14 h-14 rounded-full bg-slate-900 border border-slate-700 flex items-center justify-center mb-4 group-hover:scale-105 transition-transform group-hover:border-blue-500/50">
                  <Camera className="w-6 h-6 text-slate-400 group-hover:text-blue-400 transition-colors" />
                </div>
                <span className="text-sm font-semibold text-slate-300 text-center">
                  Drag and drop or click to browse
                </span>
                <span className="text-xs text-slate-500 mt-2 font-mono">
                  ACCEPTED: JPEG, JPG, PNG
                </span>
                <input
                  type="file"
                  accept="image/jpeg, image/png, image/jpg"
                  className="hidden"
                  onChange={(e: ChangeEvent<HTMLInputElement>) => {
                    const file = e.target.files?.[0] || null;
                    handlePhotoChange(file);
                  }}
                />
              </label>
            )}
          </div>
        </div>
      </div>

      {/* Progress / Submit Action */}
      <div className="flex flex-col items-center justify-center pt-4">
        {isUploading ? (
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 p-6 rounded-xl shadow-lg">
            <div className="flex items-center gap-3 mb-4 text-blue-400">
              <ServerCog className="w-5 h-5 animate-pulse" />
              <span className="font-mono text-sm font-semibold tracking-wider">SYSTEM PROCESSING</span>
            </div>
            
            <div className="space-y-3">
              {PROGRESS_STAGES.map((stage, idx) => (
                <div key={stage} className="flex items-center gap-3 text-sm">
                  {idx < progressStageIdx ? (
                    <CheckCircle className="w-4 h-4 text-emerald-500" />
                  ) : idx === progressStageIdx ? (
                    <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
                  ) : (
                    <div className="w-4 h-4 rounded-full border border-slate-700 bg-slate-800" />
                  )}
                  <span className={`font-mono ${
                    idx < progressStageIdx ? 'text-slate-400' :
                    idx === progressStageIdx ? 'text-slate-200 font-semibold' : 'text-slate-600'
                  }`}>
                    {stage}
                  </span>
                </div>
              ))}
            </div>
            
            <div className="w-full bg-slate-800 h-1.5 mt-6 rounded-full overflow-hidden">
              <div 
                className="bg-blue-500 h-full transition-all duration-300 ease-out" 
                style={{ width: `${Math.max(5, (progressStageIdx / (PROGRESS_STAGES.length - 1)) * 100)}%` }}
              />
            </div>
          </div>
        ) : (
          <button
            type="submit"
            disabled={!docFile || !livePhoto}
            className={`flex items-center justify-center gap-2 px-10 py-4 rounded-xl font-bold uppercase tracking-wider text-sm transition-all shadow-lg w-full max-w-sm ${
              !docFile || !livePhoto
                ? 'bg-slate-800 text-slate-500 border border-slate-700 cursor-not-allowed shadow-none'
                : 'bg-blue-600 text-white hover:bg-blue-500 active:scale-[0.98] border border-blue-500 shadow-blue-500/20'
            }`}
          >
            <Upload className="w-4 h-4" />
            <span>Screen Document</span>
          </button>
        )}
      </div>
    </form>
  );
}
