'use client';

import React, { useState, ChangeEvent } from 'react';
import { Upload, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { ScreeningResult } from '@/app/types/contracts';

export interface UploadFormProps {
  onResult: (result: ScreeningResult) => void;
  onError: (error: string) => void;
}

export default function UploadForm({ onResult, onError }: UploadFormProps) {
  const [docFile, setDocFile] = useState<File | null>(null);
  const [livePhoto, setLivePhoto] = useState<File | null>(null);
  const [docPreview, setDocPreview] = useState<string | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!docFile || !livePhoto || isUploading) return;

    setIsUploading(true);

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
          // fallback to status code message
        }
        throw new Error(errorDetail);
      }

      const result: ScreeningResult = await response.json();
      onResult(result);
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
    <form onSubmit={handleSubmit} className="w-full max-w-4xl mx-auto space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Document Upload Area */}
        <div className="flex flex-col space-y-2">
          <label className="text-sm font-semibold text-gray-700 dark:text-gray-200">
            Document Image <span className="text-red-500">*</span>
          </label>
          <div
            className={`relative border-2 border-dashed rounded-xl p-4 flex flex-col items-center justify-center transition-all min-h-[220px] ${
              docPreview
                ? 'border-emerald-500/50 bg-emerald-50/20 dark:bg-emerald-950/10'
                : 'border-gray-300 dark:border-gray-700 hover:border-blue-500/60 bg-gray-50/50 dark:bg-gray-900/40'
            }`}
          >
            {docPreview ? (
              <div className="flex flex-col items-center space-y-3 w-full">
                <div className="relative w-full h-36 rounded-lg overflow-hidden border border-emerald-300 dark:border-emerald-800 flex items-center justify-center bg-black/5 dark:bg-black/20">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={docPreview}
                    alt="Document preview"
                    className="max-h-full max-w-full object-contain"
                  />
                </div>
                <div className="flex items-center justify-between w-full px-2 text-xs text-gray-600 dark:text-gray-300">
                  <span className="flex items-center gap-1.5 font-medium text-emerald-600 dark:text-emerald-400 truncate max-w-[180px]">
                    <CheckCircle className="w-4 h-4 shrink-0" />
                    {docFile?.name}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleDocChange(null)}
                    className="text-red-500 hover:text-red-700 dark:hover:text-red-400 p-1 flex items-center gap-1"
                  >
                    <XCircle className="w-4 h-4" /> Remove
                  </button>
                </div>
              </div>
            ) : (
              <label className="flex flex-col items-center justify-center cursor-pointer w-full h-full p-4">
                <Upload className="w-10 h-10 text-gray-400 dark:text-gray-500 mb-2" />
                <span className="text-sm font-medium text-gray-700 dark:text-gray-200 text-center">
                  Click or drag passport/ID document
                </span>
                <span className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Supports JPEG, JPG, PNG
                </span>
                <input
                  id="doc-file-input"
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

        {/* Live Photo Upload Area */}
        <div className="flex flex-col space-y-2">
          <label className="text-sm font-semibold text-gray-700 dark:text-gray-200">
            Live Subject Photo <span className="text-red-500">*</span>
          </label>
          <div
            className={`relative border-2 border-dashed rounded-xl p-4 flex flex-col items-center justify-center transition-all min-h-[220px] ${
              photoPreview
                ? 'border-emerald-500/50 bg-emerald-50/20 dark:bg-emerald-950/10'
                : 'border-gray-300 dark:border-gray-700 hover:border-blue-500/60 bg-gray-50/50 dark:bg-gray-900/40'
            }`}
          >
            {photoPreview ? (
              <div className="flex flex-col items-center space-y-3 w-full">
                <div className="relative w-full h-36 rounded-lg overflow-hidden border border-emerald-300 dark:border-emerald-800 flex items-center justify-center bg-black/5 dark:bg-black/20">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={photoPreview}
                    alt="Live photo preview"
                    className="max-h-full max-w-full object-contain"
                  />
                </div>
                <div className="flex items-center justify-between w-full px-2 text-xs text-gray-600 dark:text-gray-300">
                  <span className="flex items-center gap-1.5 font-medium text-emerald-600 dark:text-emerald-400 truncate max-w-[180px]">
                    <CheckCircle className="w-4 h-4 shrink-0" />
                    {livePhoto?.name}
                  </span>
                  <button
                    type="button"
                    onClick={() => handlePhotoChange(null)}
                    className="text-red-500 hover:text-red-700 dark:hover:text-red-400 p-1 flex items-center gap-1"
                  >
                    <XCircle className="w-4 h-4" /> Remove
                  </button>
                </div>
              </div>
            ) : (
              <label className="flex flex-col items-center justify-center cursor-pointer w-full h-full p-4">
                <Upload className="w-10 h-10 text-gray-400 dark:text-gray-500 mb-2" />
                <span className="text-sm font-medium text-gray-700 dark:text-gray-200 text-center">
                  Click or drag live camera photo
                </span>
                <span className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Supports JPEG, JPG, PNG
                </span>
                <input
                  id="live-photo-input"
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

      {/* Submit Action */}
      <div className="flex justify-center pt-2">
        <button
          id="screen-submit-btn"
          type="submit"
          disabled={!docFile || !livePhoto || isUploading}
          className={`flex items-center justify-center gap-2 px-8 py-3.5 rounded-xl font-semibold text-white shadow-md transition-all ${
            !docFile || !livePhoto || isUploading
              ? 'bg-gray-400/80 cursor-not-allowed opacity-60'
              : 'bg-blue-600 hover:bg-blue-700 active:scale-[0.98] shadow-blue-500/20'
          }`}
        >
          {isUploading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Screening Document & Person...</span>
            </>
          ) : (
            <>
              <Upload className="w-5 h-5" />
              <span>Run Automated Screening</span>
            </>
          )}
        </button>
      </div>
    </form>
  );
}
