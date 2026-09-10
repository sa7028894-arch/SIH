import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  FileText,
  Image as ImageIcon,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  ShieldAlert,
  Hash,
  Calendar,
  User,
  Globe,
  Binary
} from 'lucide-react';
import { api, type PassportValidationResponse } from './services/api';

function cleanDisplayValue(val?: string | null): string {
  if (!val) return 'Not Available';
  // Strip trailing/leading chevrons and convert filler chevrons to spaces
  const cleaned = val.replace(/<+$/g, '').replace(/^<+/g, '').replace(/</g, ' ').trim();
  return cleaned || 'Not Available';
}

function formatSex(val?: string | null): string {
  if (!val || val === '<') return 'Unspecified';
  const cleaned = val.replace(/</g, '').trim().toUpperCase();
  if (cleaned === 'M') return 'Male (M)';
  if (cleaned === 'F') return 'Female (F)';
  return cleaned || 'Unspecified';
}

export default function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<PassportValidationResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const processFile = async (file: File) => {
    setSelectedFile(file);
    setIsLoading(true);
    setErrorMessage(null);
    setResult(null);

    try {
      const response = await api.validatePassport(file);
      setResult(response);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Failed to process passport file.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const file = files[0];
    const isImage = file.type.startsWith('image/');
    const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');

    if (!isImage && !isPdf) {
      setErrorMessage('Please upload a supported image (.jpg, .png, .webp) or PDF document.');
      return;
    }

    processFile(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    handleFiles(e.dataTransfer.files);
  };

  const resetUpload = () => {
    setSelectedFile(null);
    setResult(null);
    setErrorMessage(null);
    setIsLoading(false);
    if (inputRef.current) {
      inputRef.current.value = '';
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-4 sm:p-8 selection:bg-indigo-500 selection:text-white">
      <div className="w-full max-w-2xl flex flex-col gap-6">
        {/* Hidden File Input */}
        <input
          ref={inputRef}
          type="file"
          accept="image/*,application/pdf,.pdf"
          className="hidden"
          onChange={(e) => {
            handleFiles(e.target.files);
          }}
        />

        {/* Input Dropzone Area (Visible when not showing results or while loading) */}
        {!result && (
          <div
            onClick={() => !isLoading && inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              if (!isLoading) setIsDragOver(true);
            }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={handleDrop}
            className={`relative flex flex-col items-center justify-center p-10 sm:p-14 border-2 border-dashed rounded-3xl cursor-pointer transition-all duration-200 outline-none select-none ${
              isLoading
                ? 'border-indigo-500/50 bg-slate-900/60 cursor-wait'
                : isDragOver
                ? 'border-indigo-400 bg-indigo-500/10 scale-[1.01]'
                : 'border-slate-800 bg-slate-900/40 hover:border-slate-700 hover:bg-slate-900/70'
            }`}
          >
            {isLoading ? (
              <div className="flex flex-col items-center text-center">
                <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center mb-4">
                  <RefreshCw className="w-7 h-7 animate-spin" />
                </div>
                <h3 className="text-base font-semibold text-white mb-1">
                  Processing Passport OCR with Sarvam AI...
                </h3>
                <p className="text-xs text-slate-400 max-w-xs">
                  Extracting structured passport fields using Sarvam Doc AI Vision on {selectedFile?.name}.
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center text-center">
                <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center mb-4 transition-transform group-hover:scale-105">
                  <UploadCloud className="w-7 h-7" />
                </div>

                <h3 className="text-base sm:text-lg font-semibold text-white mb-1">
                  {isDragOver ? 'Drop passport file here' : 'Upload passport document'}
                </h3>
                <p className="text-xs sm:text-sm text-slate-400 max-w-md mb-4">
                  Drag and drop your passport image or PDF, or click to browse.
                </p>

                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
                    <ImageIcon className="w-3.5 h-3.5 text-indigo-400" />
                    Images (JPG, PNG, WEBP)
                  </span>
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
                    <FileText className="w-3.5 h-3.5 text-rose-400" />
                    PDF Documents
                  </span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Error Message Box */}
        {errorMessage && (
          <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs sm:text-sm flex items-start justify-between gap-3 animate-in fade-in">
            <div className="flex items-start gap-2.5">
              <XCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-white">Validation Error</p>
                <p className="mt-0.5 text-rose-300/90">{errorMessage}</p>
              </div>
            </div>
            <button
              onClick={resetUpload}
              className="px-3 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 text-xs font-medium shrink-0 transition-colors"
            >
              Try Again
            </button>
          </div>
        )}

        {/* Passport OCR & MRZ Validation Results Card */}
        {result && (
          <div className="w-full bg-slate-900/90 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl animate-in fade-in flex flex-col gap-6">
            {/* Header / Status Banner */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <div
                  className={`w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 ${
                    result.mrz_detected && result.data?.mrz_valid
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : result.mrz_detected
                      ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                      : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                  }`}
                >
                  {result.mrz_detected && result.data?.mrz_valid ? (
                    <ShieldCheck className="w-6 h-6" />
                  ) : result.mrz_detected ? (
                    <AlertTriangle className="w-6 h-6" />
                  ) : (
                    <ShieldAlert className="w-6 h-6" />
                  )}
                </div>

                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-lg text-white">
                      {result.mrz_detected && result.data?.mrz_valid
                        ? 'Passport Extracted'
                        : result.mrz_detected
                        ? 'Passport Extracted (Low Confidence)'
                        : 'No Passport Data Detected'}
                    </h3>
                    <span
                      className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full ${
                        result.mrz_detected && result.data?.mrz_valid
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : result.mrz_detected
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                      }`}
                    >
                      {result.data?.valid_score ?? 0}% Score
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">{result.message}</p>
                </div>
              </div>

              {/* Reset / Upload Another Button */}
              <button
                onClick={resetUpload}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 hover:text-white transition-colors border border-slate-700 self-start sm:self-auto"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Upload Another
              </button>
            </div>

            {/* Extracted Fields Grid */}
            {result.data && (
              <div className="flex flex-col gap-6">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                  {/* Full Name */}
                  <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                    <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                      <User className="w-3.5 h-3.5 text-indigo-400" />
                      FULL NAME
                    </div>
                    <p className="text-sm font-semibold text-white truncate">
                      {cleanDisplayValue(result.data.name)}
                    </p>
                  </div>

                  {/* Document Number */}
                  <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                    <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                      <Hash className="w-3.5 h-3.5 text-indigo-400" />
                      DOCUMENT / PASSPORT NUMBER
                    </div>
                    <p className="text-sm font-semibold text-white font-mono">
                      {cleanDisplayValue(result.data.document_number)}
                    </p>
                  </div>

                  {/* Nationality & Country */}
                  <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                    <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                      <Globe className="w-3.5 h-3.5 text-indigo-400" />
                      NATIONALITY / ISSUING COUNTRY
                    </div>
                    <p className="text-sm font-semibold text-white">
                      {cleanDisplayValue(result.data.nationality || result.data.country)}
                    </p>
                  </div>

                  {/* Sex */}
                  <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                    <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                      <User className="w-3.5 h-3.5 text-indigo-400" />
                      SEX
                    </div>
                    <p className="text-sm font-semibold text-white">
                      {formatSex(result.data.sex)}
                    </p>
                  </div>

                  {/* Date of Birth */}
                  <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                    <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                      <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                      DATE OF BIRTH (YYMMDD)
                    </div>
                    <p className="text-sm font-semibold text-white font-mono">
                      {cleanDisplayValue(result.data.date_of_birth)}
                    </p>
                  </div>

                  {/* Expiry Date */}
                  <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                    <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                      <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                      EXPIRATION DATE (YYMMDD)
                    </div>
                    <p className="text-sm font-semibold text-white font-mono">
                      {cleanDisplayValue(result.data.expiry_date)}
                    </p>
                  </div>

                  {/* Date of Issue (if available) */}
                  {result.data.date_of_issue && (
                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                        DATE OF ISSUE
                      </div>
                      <p className="text-sm font-semibold text-white font-mono">
                        {cleanDisplayValue(result.data.date_of_issue)}
                      </p>
                    </div>
                  )}

                  {/* Place of Issue (if available) */}
                  {result.data.place_of_issue && (
                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <Globe className="w-3.5 h-3.5 text-indigo-400" />
                        PLACE OF ISSUE
                      </div>
                      <p className="text-sm font-semibold text-white">
                        {cleanDisplayValue(result.data.place_of_issue)}
                      </p>
                    </div>
                  )}
                </div>

                {/* Check Digit Status Pills (rendered only if checksum validation was performed) */}
                {result.data.check_digits &&
                  (result.data.check_digits.number !== null ||
                    result.data.check_digits.date_of_birth !== null ||
                    result.data.check_digits.expiration_date !== null) && (
                    <div className="p-4 rounded-2xl bg-slate-950/40 border border-slate-800/80">
                      <div className="text-[11px] font-medium text-slate-400 uppercase mb-2.5">
                        ICAO 9303 Check Digit Validations
                      </div>
                      <div className="flex flex-wrap gap-2 text-xs">
                        <span
                          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg border ${
                            result.data.check_digits.number
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                          }`}
                        >
                          {result.data.check_digits.number ? (
                            <CheckCircle2 className="w-3.5 h-3.5" />
                          ) : (
                            <XCircle className="w-3.5 h-3.5" />
                          )}
                          Document Number
                        </span>

                        <span
                          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg border ${
                            result.data.check_digits.date_of_birth
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                          }`}
                        >
                          {result.data.check_digits.date_of_birth ? (
                            <CheckCircle2 className="w-3.5 h-3.5" />
                          ) : (
                            <XCircle className="w-3.5 h-3.5" />
                          )}
                          Date of Birth
                        </span>

                        <span
                          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg border ${
                            result.data.check_digits.expiration_date
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                          }`}
                        >
                          {result.data.check_digits.expiration_date ? (
                            <CheckCircle2 className="w-3.5 h-3.5" />
                          ) : (
                            <XCircle className="w-3.5 h-3.5" />
                          )}
                          Expiration Date
                        </span>

                        {result.data.check_digits.composite !== null && (
                          <span
                            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg border ${
                              result.data.check_digits.composite
                                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                                : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                            }`}
                          >
                            {result.data.check_digits.composite ? (
                              <CheckCircle2 className="w-3.5 h-3.5" />
                            ) : (
                              <XCircle className="w-3.5 h-3.5" />
                            )}
                            Composite Checksum
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                {/* Raw MRZ Lines */}
                {result.data.raw_text && (
                  <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800">
                    <div className="flex items-center gap-2 text-[11px] font-medium text-slate-400 mb-2">
                      <Binary className="w-3.5 h-3.5 text-indigo-400" />
                      RAW MRZ TEXT
                    </div>
                    <pre className="font-mono text-xs text-indigo-300 whitespace-pre-wrap leading-relaxed overflow-x-auto">
                      {result.data.raw_text}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
