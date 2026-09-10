import React, { useState, useRef, useEffect } from 'react';
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
  Binary,
  Clock,
  MapPin,
  CreditCard,
  Fingerprint,
  Camera,
  ScanFace,
} from 'lucide-react';
import {
  api,
  type PassportValidationResponse,
  type EVisaValidationResponse,
  type AadhaarValidationResponse,
  type FaceCompareResponse,
} from './services/api';

function cleanDisplayValue(val?: string | null): string {
  if (!val) return 'Not Available';
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
  const [docType, setDocType] = useState<'passport' | 'evisa' | 'aadhaar' | 'face'>('passport');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [passportResult, setPassportResult] = useState<PassportValidationResponse | null>(null);
  const [evisaResult, setEVisaResult] = useState<EVisaValidationResponse | null>(null);
  const [aadhaarResult, setAadhaarResult] = useState<AadhaarValidationResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Face Comparison State
  const [docFaceFile, setDocFaceFile] = useState<File | null>(null);
  const [docFacePreview, setDocFacePreview] = useState<string | null>(null);
  const [liveFaceFile, setLiveFaceFile] = useState<File | null>(null);
  const [liveFacePreview, setLiveFacePreview] = useState<string | null>(null);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [isComparingFaces, setIsComparingFaces] = useState(false);
  const [faceCompareResult, setFaceCompareResult] = useState<FaceCompareResponse | null>(null);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const docFaceInputRef = useRef<HTMLInputElement>(null);
  const liveFaceInputRef = useRef<HTMLInputElement>(null);

  const getDocTypeName = () => {
    if (docType === 'passport') return 'Passport';
    if (docType === 'evisa') return 'E-Visa';
    if (docType === 'aadhaar') return 'Aadhaar Card';
    return 'Face Comparison';
  };

  const setVideoRef = (video: HTMLVideoElement | null) => {
    videoRef.current = video;
    if (video && streamRef.current) {
      video.srcObject = streamRef.current;
      video.play().catch((err) => console.warn('Camera video play interrupted:', err));
    }
  };

  const startCamera = async () => {
    setCameraError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
        audio: false,
      });
      streamRef.current = stream;
      setIsCameraActive(true);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play().catch((err) => console.warn('Camera video play interrupted:', err));
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unable to access camera';
      setCameraError(msg);
      setIsCameraActive(false);
    }
  };

  const stopCamera = () => {
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.srcObject = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setIsCameraActive(false);
  };

  // Clean up camera stream if component unmounts
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
    };
  }, []);

  const capturePhoto = () => {
    if (!videoRef.current) return;
    const video = videoRef.current;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob((blob) => {
      if (!blob) return;
      const file = new File([blob], 'live_webcam_snapshot.jpg', { type: 'image/jpeg' });
      setLiveFaceFile(file);
      setLiveFacePreview(URL.createObjectURL(blob));
      stopCamera();
    }, 'image/jpeg', 0.95);
  };

  const handleRunFaceCompare = async () => {
    if (!docFaceFile || !liveFaceFile) return;
    setIsComparingFaces(true);
    setErrorMessage(null);
    setFaceCompareResult(null);

    try {
      const response = await api.compareFaces(docFaceFile, liveFaceFile);
      setFaceCompareResult(response);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Face comparison failed.');
    } finally {
      setIsComparingFaces(false);
    }
  };

  const processFile = async (file: File) => {
    setSelectedFile(file);
    setIsLoading(true);
    setErrorMessage(null);
    setPassportResult(null);
    setEVisaResult(null);
    setAadhaarResult(null);

    try {
      if (docType === 'passport') {
        const response = await api.validatePassport(file);
        setPassportResult(response);
      } else if (docType === 'evisa') {
        const response = await api.validateEVisa(file);
        setEVisaResult(response);
      } else if (docType === 'aadhaar') {
        const response = await api.validateAadhaar(file);
        setAadhaarResult(response);
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage(`Failed to process ${getDocTypeName().toLowerCase()} file.`);
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
    setPassportResult(null);
    setEVisaResult(null);
    setAadhaarResult(null);
    setErrorMessage(null);
    setIsLoading(false);
    stopCamera();
    setDocFaceFile(null);
    setDocFacePreview(null);
    setLiveFaceFile(null);
    setLiveFacePreview(null);
    setFaceCompareResult(null);
    setIsComparingFaces(false);
    if (inputRef.current) {
      inputRef.current.value = '';
    }
    if (docFaceInputRef.current) {
      docFaceInputRef.current.value = '';
    }
    if (liveFaceInputRef.current) {
      liveFaceInputRef.current.value = '';
    }
  };

  const hasResult =
    docType === 'face'
      ? Boolean(faceCompareResult)
      : Boolean(passportResult || evisaResult || aadhaarResult);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-4 sm:p-8 selection:bg-indigo-500 selection:text-white">
      <div className="w-full max-w-2xl flex flex-col gap-6">
        {/* Document Type Selector Tabs */}
        {!hasResult && (
          <div className="flex items-center justify-center p-1 bg-slate-900/80 border border-slate-800 rounded-2xl w-full max-w-md mx-auto">
            <button
              onClick={() => {
                setDocType('passport');
                resetUpload();
              }}
              className={`flex-1 py-2 px-2 sm:px-3 rounded-xl text-xs font-semibold transition-all ${
                docType === 'passport'
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Passport
            </button>
            <button
              onClick={() => {
                setDocType('evisa');
                resetUpload();
              }}
              className={`flex-1 py-2 px-2 sm:px-3 rounded-xl text-xs font-semibold transition-all ${
                docType === 'evisa'
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              E-Visa
            </button>
            <button
              onClick={() => {
                setDocType('aadhaar');
                resetUpload();
              }}
              className={`flex-1 py-2 px-2 sm:px-3 rounded-xl text-xs font-semibold transition-all ${
                docType === 'aadhaar'
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Aadhaar
            </button>
            <button
              onClick={() => {
                setDocType('face');
                resetUpload();
              }}
              className={`flex-1 py-2 px-2 sm:px-3 rounded-xl text-xs font-semibold transition-all flex items-center justify-center gap-1 ${
                docType === 'face'
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <ScanFace className="w-3.5 h-3.5" />
              Face Match
            </button>
          </div>
        )}

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

        {/* Input Dropzone Area for Document OCR (Visible when not showing results or while loading) */}
        {!hasResult && docType !== 'face' && (
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
                  Processing {getDocTypeName()} with Sarvam AI...
                </h3>
                <p className="text-xs text-slate-400 max-w-xs">
                  Extracting structured fields using Sarvam Doc AI Vision on {selectedFile?.name}.
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center text-center">
                <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center mb-4 transition-transform group-hover:scale-105">
                  <UploadCloud className="w-7 h-7" />
                </div>

                <h3 className="text-base sm:text-lg font-semibold text-white mb-1">
                  {isDragOver
                    ? `Drop ${getDocTypeName().toLowerCase()} file here`
                    : `Upload ${getDocTypeName()} document`}
                </h3>
                <p className="text-xs sm:text-sm text-slate-400 max-w-md mb-4">
                  Drag and drop your {getDocTypeName().toLowerCase()} image or PDF, or click to browse.
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

        {/* Face Comparison Input Panel (Reference Pic + Live Pic) */}
        {!hasResult && docType === 'face' && (
          <div className="flex flex-col gap-6 bg-slate-900/70 border border-slate-800 rounded-3xl p-6 sm:p-8">
            <div className="text-center mb-1">
              <h2 className="text-base sm:text-lg font-bold text-white flex items-center justify-center gap-2">
                <ScanFace className="w-5 h-5 text-indigo-400" />
                Real-Time Face Match (OpenFace)
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Provide a reference photo and compare it against a live camera snapshot in real time.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Step 1: Reference Document Photo */}
              <div className="flex flex-col gap-3 p-4 rounded-2xl bg-slate-950/70 border border-slate-800">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wider flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5" />
                    1. Reference Photo / Document
                  </span>
                  {docFaceFile && (
                    <button
                      onClick={() => {
                        setDocFaceFile(null);
                        setDocFacePreview(null);
                      }}
                      className="text-[10px] text-slate-400 hover:text-rose-400 transition-colors"
                    >
                      Change
                    </button>
                  )}
                </div>

                <input
                  ref={docFaceInputRef}
                  type="file"
                  accept="image/*,application/pdf,.pdf"
                  className="hidden"
                  onChange={(e) => {
                    const files = e.target.files;
                    if (files && files[0]) {
                      const f = files[0];
                      setDocFaceFile(f);
                      setDocFacePreview(URL.createObjectURL(f));
                    }
                  }}
                />

                {docFacePreview ? (
                  <div className="relative w-full h-44 rounded-xl overflow-hidden bg-slate-900 border border-slate-800 flex items-center justify-center">
                    <img src={docFacePreview} alt="Reference" className="w-full h-full object-contain" />
                  </div>
                ) : (
                  <div
                    onClick={() => docFaceInputRef.current?.click()}
                    className="flex flex-col items-center justify-center h-44 border-2 border-dashed border-slate-800 hover:border-indigo-500/50 rounded-xl cursor-pointer bg-slate-900/30 hover:bg-slate-900/50 transition-all p-4 text-center"
                  >
                    <UploadCloud className="w-7 h-7 text-indigo-400 mb-2" />
                    <p className="text-xs font-medium text-white">Upload ID or Photo</p>
                    <p className="text-[10px] text-slate-400 mt-1">Passport, Visa, Aadhaar, or portrait</p>
                  </div>
                )}
              </div>

              {/* Step 2: Live Picture / Camera */}
              <div className="flex flex-col gap-3 p-4 rounded-2xl bg-slate-950/70 border border-slate-800">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
                    <Camera className="w-3.5 h-3.5" />
                    2. Live Picture
                  </span>
                  {liveFaceFile && (
                    <button
                      onClick={() => {
                        setLiveFaceFile(null);
                        setLiveFacePreview(null);
                      }}
                      className="text-[10px] text-slate-400 hover:text-rose-400 transition-colors"
                    >
                      Retake
                    </button>
                  )}
                </div>

                <input
                  ref={liveFaceInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => {
                    const files = e.target.files;
                    if (files && files[0]) {
                      const f = files[0];
                      setLiveFaceFile(f);
                      setLiveFacePreview(URL.createObjectURL(f));
                    }
                  }}
                />

                {isCameraActive ? (
                  <div className="relative w-full h-44 rounded-xl overflow-hidden bg-black flex items-center justify-center">
                    <video ref={setVideoRef} autoPlay playsInline muted className="w-full h-full object-cover scale-x-[-1]" />
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                      <div className="w-24 h-32 border-2 border-dashed border-emerald-400/80 rounded-full" />
                    </div>
                    <div className="absolute bottom-2 flex gap-2">
                      <button
                        onClick={capturePhoto}
                        className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-bold shadow-lg transition-all flex items-center gap-1"
                      >
                        <Camera className="w-3 h-3" />
                        Take Snapshot
                      </button>
                      <button
                        onClick={stopCamera}
                        className="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] transition-all"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : liveFacePreview ? (
                  <div className="relative w-full h-44 rounded-xl overflow-hidden bg-slate-900 border border-slate-800 flex items-center justify-center">
                    <img src={liveFacePreview} alt="Live Capture" className="w-full h-full object-contain" />
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-44 border-2 border-dashed border-slate-800 rounded-xl bg-slate-900/30 p-4 text-center gap-2">
                    <button
                      onClick={startCamera}
                      className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-600/20 transition-all flex items-center gap-1.5"
                    >
                      <Camera className="w-3.5 h-3.5" />
                      Open Live Camera
                    </button>
                    <span className="text-[10px] text-slate-500">or</span>
                    <button
                      onClick={() => liveFaceInputRef.current?.click()}
                      className="text-xs text-slate-400 hover:text-white transition-colors underline"
                    >
                      Upload Selfie Image
                    </button>
                    {cameraError && (
                      <p className="text-[10px] text-rose-400 mt-1">{cameraError}</p>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Compare Button */}
            <div className="flex flex-col items-center justify-center pt-1">
              <button
                disabled={!docFaceFile || !liveFaceFile || isComparingFaces}
                onClick={handleRunFaceCompare}
                className={`w-full max-w-sm py-2.5 px-5 rounded-xl font-bold text-xs flex items-center justify-center gap-2 transition-all ${
                  docFaceFile && liveFaceFile && !isComparingFaces
                    ? 'bg-gradient-to-r from-indigo-600 to-emerald-600 text-white shadow-xl shadow-indigo-600/20 hover:scale-[1.01] cursor-pointer'
                    : 'bg-slate-800 text-slate-500 cursor-not-allowed'
                }`}
              >
                {isComparingFaces ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    Extracting & Comparing with OpenFace...
                  </>
                ) : (
                  <>
                    <ScanFace className="w-4 h-4" />
                    Compare Faces Real-Time
                  </>
                )}
              </button>
              {(!docFaceFile || !liveFaceFile) && (
                <p className="text-[10px] text-slate-500 mt-2">
                  Provide both reference photo and live picture to run OpenFace comparison.
                </p>
              )}
            </div>
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
        {passportResult && (
          <div className="w-full bg-slate-900/90 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl animate-in fade-in flex flex-col gap-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <div
                  className={`w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 ${
                    passportResult.mrz_detected && passportResult.data?.mrz_valid
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : passportResult.mrz_detected
                      ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                      : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                  }`}
                >
                  {passportResult.mrz_detected && passportResult.data?.mrz_valid ? (
                    <ShieldCheck className="w-6 h-6" />
                  ) : passportResult.mrz_detected ? (
                    <AlertTriangle className="w-6 h-6" />
                  ) : (
                    <ShieldAlert className="w-6 h-6" />
                  )}
                </div>

                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-lg text-white">
                      {passportResult.mrz_detected && passportResult.data?.mrz_valid
                        ? 'Passport Extracted'
                        : passportResult.mrz_detected
                        ? 'Passport Extracted (Low Confidence)'
                        : 'No Passport Data Detected'}
                    </h3>
                    <span
                      className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full ${
                        passportResult.mrz_detected && passportResult.data?.mrz_valid
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : passportResult.mrz_detected
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                      }`}
                    >
                      {passportResult.data?.valid_score ?? 0}% Score
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">{passportResult.message}</p>
                </div>
              </div>

              <button
                onClick={resetUpload}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 hover:text-white transition-colors border border-slate-700 self-start sm:self-auto"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Upload Another
              </button>
            </div>

            {passportResult.data && (
              <div className="flex flex-col gap-6">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                  <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                    <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                      <User className="w-3.5 h-3.5 text-indigo-400" />
                      FULL NAME
                    </div>
                    <p className="text-sm font-semibold text-white truncate">
                      {cleanDisplayValue(passportResult.data.name)}
                    </p>
                  </div>

                  <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                    <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                      <Hash className="w-3.5 h-3.5 text-indigo-400" />
                      DOCUMENT / PASSPORT NUMBER
                    </div>
                    <p className="text-sm font-semibold text-white font-mono">
                      {cleanDisplayValue(passportResult.data.document_number)}
                    </p>
                  </div>

                  <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                    <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                      <Globe className="w-3.5 h-3.5 text-indigo-400" />
                      NATIONALITY / ISSUING COUNTRY
                    </div>
                    <p className="text-sm font-semibold text-white">
                      {cleanDisplayValue(passportResult.data.nationality || passportResult.data.country)}
                    </p>
                  </div>

                  <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                    <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                      <User className="w-3.5 h-3.5 text-indigo-400" />
                      SEX
                    </div>
                    <p className="text-sm font-semibold text-white">
                      {formatSex(passportResult.data.sex)}
                    </p>
                  </div>

                  <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                    <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                      <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                      DATE OF BIRTH
                    </div>
                    <p className="text-sm font-semibold text-white font-mono">
                      {cleanDisplayValue(passportResult.data.date_of_birth)}
                    </p>
                  </div>

                  <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                    <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                      <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                      EXPIRATION DATE
                    </div>
                    <p className="text-sm font-semibold text-white font-mono">
                      {cleanDisplayValue(passportResult.data.expiry_date)}
                    </p>
                  </div>

                  {passportResult.data.date_of_issue && (
                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                        DATE OF ISSUE
                      </div>
                      <p className="text-sm font-semibold text-white font-mono">
                        {cleanDisplayValue(passportResult.data.date_of_issue)}
                      </p>
                    </div>
                  )}

                  {passportResult.data.place_of_issue && (
                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <Globe className="w-3.5 h-3.5 text-indigo-400" />
                        PLACE OF ISSUE
                      </div>
                      <p className="text-sm font-semibold text-white">
                        {cleanDisplayValue(passportResult.data.place_of_issue)}
                      </p>
                    </div>
                  )}
                </div>

                {passportResult.data.check_digits &&
                  (passportResult.data.check_digits.number !== null ||
                    passportResult.data.check_digits.date_of_birth !== null ||
                    passportResult.data.check_digits.expiration_date !== null) && (
                    <div className="p-4 rounded-2xl bg-slate-950/40 border border-slate-800/80">
                      <div className="text-[11px] font-medium text-slate-400 uppercase mb-2.5">
                        ICAO 9303 Check Digit Validations
                      </div>
                      <div className="flex flex-wrap gap-2 text-xs">
                        <span
                          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg border ${
                            passportResult.data.check_digits.number
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                          }`}
                        >
                          {passportResult.data.check_digits.number ? (
                            <CheckCircle2 className="w-3.5 h-3.5" />
                          ) : (
                            <XCircle className="w-3.5 h-3.5" />
                          )}
                          Document Number
                        </span>

                        <span
                          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg border ${
                            passportResult.data.check_digits.date_of_birth
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                          }`}
                        >
                          {passportResult.data.check_digits.date_of_birth ? (
                            <CheckCircle2 className="w-3.5 h-3.5" />
                          ) : (
                            <XCircle className="w-3.5 h-3.5" />
                          )}
                          Date of Birth
                        </span>

                        <span
                          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg border ${
                            passportResult.data.check_digits.expiration_date
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                          }`}
                        >
                          {passportResult.data.check_digits.expiration_date ? (
                            <CheckCircle2 className="w-3.5 h-3.5" />
                          ) : (
                            <XCircle className="w-3.5 h-3.5" />
                          )}
                          Expiration Date
                        </span>

                        {passportResult.data.check_digits.composite !== null && (
                          <span
                            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg border ${
                              passportResult.data.check_digits.composite
                                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                                : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                            }`}
                          >
                            {passportResult.data.check_digits.composite ? (
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

                {passportResult.data.raw_text && (
                  <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800">
                    <div className="flex items-center gap-2 text-[11px] font-medium text-slate-400 mb-2">
                      <Binary className="w-3.5 h-3.5 text-indigo-400" />
                      RAW MRZ TEXT
                    </div>
                    <pre className="font-mono text-xs text-indigo-300 whitespace-pre-wrap leading-relaxed overflow-x-auto">
                      {passportResult.data.raw_text}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* E-Visa Validation Results Card */}
        {evisaResult && (
          <div className="w-full bg-slate-900/90 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl animate-in fade-in flex flex-col gap-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <div
                  className={`w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 ${
                    evisaResult.visa_detected && evisaResult.data?.visa_valid
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : evisaResult.visa_detected
                      ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                      : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                  }`}
                >
                  {evisaResult.visa_detected && evisaResult.data?.visa_valid ? (
                    <ShieldCheck className="w-6 h-6" />
                  ) : evisaResult.visa_detected ? (
                    <AlertTriangle className="w-6 h-6" />
                  ) : (
                    <ShieldAlert className="w-6 h-6" />
                  )}
                </div>

                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-lg text-white">
                      {evisaResult.visa_detected && evisaResult.data?.visa_valid
                        ? 'E-Visa Extracted'
                        : evisaResult.visa_detected
                        ? 'E-Visa Detected (Low Confidence)'
                        : 'No E-Visa Data Detected'}
                    </h3>
                    <span
                      className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full ${
                        evisaResult.visa_detected && evisaResult.data?.visa_valid
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : evisaResult.visa_detected
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                      }`}
                    >
                      {evisaResult.data?.valid_score ?? 0}% Score
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">{evisaResult.message}</p>
                </div>
              </div>

              <button
                onClick={resetUpload}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 hover:text-white transition-colors border border-slate-700 self-start sm:self-auto"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Upload Another
              </button>
            </div>

            {evisaResult.data && (
              <div className="flex flex-col gap-6">
                {/* Visa Authorization Section */}
                <div>
                  <div className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wider mb-3">
                    Visa Authorization
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <CreditCard className="w-3.5 h-3.5 text-indigo-400" />
                        VISA NUMBER
                      </div>
                      <p className="text-sm font-semibold text-white font-mono">
                        {cleanDisplayValue(evisaResult.data.visa_number)}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <FileText className="w-3.5 h-3.5 text-indigo-400" />
                        VISA TYPE / PURPOSE
                      </div>
                      <p className="text-sm font-semibold text-white">
                        {cleanDisplayValue(evisaResult.data.visa_type)}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <Clock className="w-3.5 h-3.5 text-indigo-400" />
                        PERMITTED STAY DURATION
                      </div>
                      <p className="text-sm font-semibold text-white">
                        {cleanDisplayValue(evisaResult.data.stay_duration)}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                        ENTRY VALIDATION / PERIOD
                      </div>
                      <p className="text-sm font-semibold text-white font-mono">
                        {cleanDisplayValue(evisaResult.data.entry_validation)}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Passport Information Section */}
                <div>
                  <div className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wider mb-3">
                    Associated Passport
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <Hash className="w-3.5 h-3.5 text-indigo-400" />
                        PASSPORT NUMBER
                      </div>
                      <p className="text-sm font-semibold text-white font-mono">
                        {cleanDisplayValue(evisaResult.data.passport_number)}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <Globe className="w-3.5 h-3.5 text-indigo-400" />
                        ISSUING COUNTRY
                      </div>
                      <p className="text-sm font-semibold text-white">
                        {cleanDisplayValue(evisaResult.data.passport_issuing_country)}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                        PASSPORT ISSUE DATE
                      </div>
                      <p className="text-sm font-semibold text-white font-mono">
                        {cleanDisplayValue(evisaResult.data.passport_issue_date)}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                        PASSPORT EXPIRY DATE
                      </div>
                      <p className="text-sm font-semibold text-white font-mono">
                        {cleanDisplayValue(evisaResult.data.passport_expiration_date)}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Personal Details Section */}
                <div>
                  <div className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wider mb-3">
                    Holder Identity
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <User className="w-3.5 h-3.5 text-indigo-400" />
                        FULL NAME
                      </div>
                      <p className="text-sm font-semibold text-white truncate">
                        {cleanDisplayValue(evisaResult.data.name)}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <Globe className="w-3.5 h-3.5 text-indigo-400" />
                        NATIONALITY
                      </div>
                      <p className="text-sm font-semibold text-white">
                        {cleanDisplayValue(evisaResult.data.nationality)}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                        DATE OF BIRTH
                      </div>
                      <p className="text-sm font-semibold text-white font-mono">
                        {cleanDisplayValue(evisaResult.data.dob)}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <MapPin className="w-3.5 h-3.5 text-indigo-400" />
                        PLACE OF BIRTH
                      </div>
                      <p className="text-sm font-semibold text-white">
                        {cleanDisplayValue(evisaResult.data.place_of_birth)}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <User className="w-3.5 h-3.5 text-indigo-400" />
                        SEX
                      </div>
                      <p className="text-sm font-semibold text-white">
                        {formatSex(evisaResult.data.sex)}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Aadhaar Validation Results Card */}
        {aadhaarResult && (
          <div className="w-full bg-slate-900/90 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl animate-in fade-in flex flex-col gap-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <div
                  className={`w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 ${
                    aadhaarResult.aadhaar_detected && aadhaarResult.data?.aadhaar_valid
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : aadhaarResult.aadhaar_detected
                      ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                      : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                  }`}
                >
                  {aadhaarResult.aadhaar_detected && aadhaarResult.data?.aadhaar_valid ? (
                    <ShieldCheck className="w-6 h-6" />
                  ) : aadhaarResult.aadhaar_detected ? (
                    <AlertTriangle className="w-6 h-6" />
                  ) : (
                    <ShieldAlert className="w-6 h-6" />
                  )}
                </div>

                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-lg text-white">
                      {aadhaarResult.aadhaar_detected && aadhaarResult.data?.aadhaar_valid
                        ? 'Aadhaar Card Verified'
                        : aadhaarResult.aadhaar_detected
                        ? 'Aadhaar Extracted (Needs Review)'
                        : 'No Aadhaar Data Detected'}
                    </h3>
                    <span
                      className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full ${
                        aadhaarResult.aadhaar_detected && aadhaarResult.data?.aadhaar_valid
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : aadhaarResult.aadhaar_detected
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                      }`}
                    >
                      {aadhaarResult.data?.valid_score ?? 0}% Score
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">{aadhaarResult.message}</p>
                </div>
              </div>

              <button
                onClick={resetUpload}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 hover:text-white transition-colors border border-slate-700 self-start sm:self-auto"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Upload Another
              </button>
            </div>

            {aadhaarResult.data && (
              <div className="flex flex-col gap-6">
                {/* Aadhaar UID & Checksum Section */}
                <div>
                  <div className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wider mb-3">
                    Aadhaar Identification Number
                  </div>
                  <div className="p-4 rounded-2xl bg-slate-950/60 border border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center shrink-0">
                        <Fingerprint className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="text-[11px] font-medium text-slate-400 mb-0.5">
                          12-DIGIT AADHAAR NUMBER
                        </div>
                        <div className="text-lg sm:text-xl font-bold font-mono tracking-wider text-white">
                          {aadhaarResult.data.formatted_aadhaar_no || cleanDisplayValue(aadhaarResult.data.aadhaar_no)}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center">
                      {aadhaarResult.data.checksum_valid === true && (
                        <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          <CheckCircle2 className="w-4 h-4" />
                          Verhoeff Checksum Valid
                        </span>
                      )}
                      {aadhaarResult.data.checksum_valid === false && (
                        <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
                          <XCircle className="w-4 h-4" />
                          Verhoeff Checksum Invalid
                        </span>
                      )}
                      {aadhaarResult.data.checksum_valid === null && (
                        <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700">
                          Checksum Unverified
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Cardholder Identity Details Section */}
                <div>
                  <div className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wider mb-3">
                    Cardholder Details
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <User className="w-3.5 h-3.5 text-indigo-400" />
                        FULL NAME
                      </div>
                      <p className="text-sm font-semibold text-white truncate">
                        {cleanDisplayValue(aadhaarResult.data.name)}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                        DATE OF BIRTH
                      </div>
                      <p className="text-sm font-semibold text-white font-mono">
                        {cleanDisplayValue(aadhaarResult.data.dob)}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                        <User className="w-3.5 h-3.5 text-indigo-400" />
                        GENDER / SEX
                      </div>
                      <p className="text-sm font-semibold text-white">
                        {cleanDisplayValue(aadhaarResult.data.sex)}
                      </p>
                    </div>

                    {aadhaarResult.data.first_name && (
                      <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                        <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                          <User className="w-3.5 h-3.5 text-indigo-400" />
                          FIRST NAME
                        </div>
                        <p className="text-sm font-semibold text-white">
                          {cleanDisplayValue(aadhaarResult.data.first_name)}
                        </p>
                      </div>
                    )}

                    {aadhaarResult.data.last_name && (
                      <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80">
                        <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 mb-1">
                          <User className="w-3.5 h-3.5 text-indigo-400" />
                          LAST NAME
                        </div>
                        <p className="text-sm font-semibold text-white">
                          {cleanDisplayValue(aadhaarResult.data.last_name)}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Face Comparison Results Card */}
        {faceCompareResult && (
          <div className="w-full bg-slate-900/90 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl animate-in fade-in flex flex-col gap-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <div
                  className={`w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 ${
                    faceCompareResult.is_match
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                  }`}
                >
                  {faceCompareResult.is_match ? (
                    <ShieldCheck className="w-6 h-6" />
                  ) : (
                    <ShieldAlert className="w-6 h-6" />
                  )}
                </div>

                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-lg text-white">
                      {faceCompareResult.is_match ? 'Identity Verified' : 'Identity Mismatch'}
                    </h3>
                    <span
                      className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full ${
                        faceCompareResult.is_match
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                      }`}
                    >
                      {faceCompareResult.similarity_score}% Match
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {faceCompareResult.message}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 self-end sm:self-auto">
                <button
                  onClick={resetUpload}
                  className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors flex items-center gap-1.5"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  Compare Another
                </button>
              </div>
            </div>

            {/* Side-by-side Face Inspection */}
            <div>
              <div className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wider mb-3">
                Extracted Faces & Comparison Inspection
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Document Reference Face */}
                <div className="p-4 rounded-2xl bg-slate-950/60 border border-slate-800/80 flex flex-col items-center">
                  <span className="text-[11px] font-medium text-slate-400 mb-2 flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-indigo-400" />
                    Reference Document Face
                  </span>
                  <div className="w-36 h-36 rounded-2xl overflow-hidden bg-slate-900 border border-slate-700/80 flex items-center justify-center relative shadow-inner">
                    {faceCompareResult.doc_face?.image_base64 ? (
                      <img
                        src={faceCompareResult.doc_face.image_base64}
                        alt="Extracted Doc Face"
                        className="w-full h-full object-cover"
                      />
                    ) : docFacePreview ? (
                      <img
                        src={docFacePreview}
                        alt="Uploaded Document"
                        className="w-full h-full object-contain"
                      />
                    ) : (
                      <span className="text-xs text-slate-500">No Face</span>
                    )}
                    {faceCompareResult.doc_face?.face_detected && (
                      <span className="absolute bottom-1 right-1 text-[9px] bg-black/70 text-emerald-400 px-1.5 py-0.5 rounded font-mono">
                        {Math.round(faceCompareResult.doc_face.confidence * 100)}% Conf
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-400 mt-2 truncate max-w-full">
                    {docFaceFile?.name || 'Document photo'}
                  </p>
                </div>

                {/* Live Captured Face */}
                <div className="p-4 rounded-2xl bg-slate-950/60 border border-slate-800/80 flex flex-col items-center">
                  <span className="text-[11px] font-medium text-slate-400 mb-2 flex items-center gap-1.5">
                    <Camera className="w-3.5 h-3.5 text-emerald-400" />
                    Live Captured Face
                  </span>
                  <div className="w-36 h-36 rounded-2xl overflow-hidden bg-slate-900 border border-slate-700/80 flex items-center justify-center relative shadow-inner">
                    {faceCompareResult.live_face?.image_base64 ? (
                      <img
                        src={faceCompareResult.live_face.image_base64}
                        alt="Live Extracted Face"
                        className="w-full h-full object-cover"
                      />
                    ) : liveFacePreview ? (
                      <img
                        src={liveFacePreview}
                        alt="Live Preview"
                        className="w-full h-full object-contain"
                      />
                    ) : (
                      <span className="text-xs text-slate-500">No Face</span>
                    )}
                    {faceCompareResult.live_face?.face_detected && (
                      <span className="absolute bottom-1 right-1 text-[9px] bg-black/70 text-emerald-400 px-1.5 py-0.5 rounded font-mono">
                        {Math.round(faceCompareResult.live_face.confidence * 100)}% Conf
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-400 mt-2 truncate max-w-full">
                    {liveFaceFile?.name || 'Live capture'}
                  </p>
                </div>
              </div>
            </div>

            {/* Match Score & OpenFace Metrics */}
            <div className="p-4 rounded-2xl bg-slate-950/60 border border-slate-800/80 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300">OpenFace Similarity Score</span>
                <span
                  className={`text-sm font-bold font-mono ${
                    faceCompareResult.is_match ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {faceCompareResult.similarity_score}%
                </span>
              </div>
              <div className="w-full h-2.5 rounded-full bg-slate-800 overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 ${
                    faceCompareResult.is_match
                      ? 'bg-gradient-to-r from-emerald-500 to-teal-400'
                      : 'bg-gradient-to-r from-rose-500 to-amber-500'
                  }`}
                  style={{ width: `${Math.min(100, Math.max(0, faceCompareResult.similarity_score))}%` }}
                />
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-2 border-t border-slate-800/60 text-xs">
                <div>
                  <span className="text-[10px] text-slate-500 uppercase block">Distance</span>
                  <span className="font-mono font-semibold text-white">
                    {faceCompareResult.distance.toFixed(4)}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 uppercase block">Match Threshold</span>
                  <span className="font-mono text-slate-400">
                    &le; {faceCompareResult.threshold.toFixed(2)}
                  </span>
                </div>
                <div className="col-span-2 sm:col-span-1">
                  <span className="text-[10px] text-slate-500 uppercase block">Verdict</span>
                  <span
                    className={`font-semibold ${
                      faceCompareResult.is_match ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {faceCompareResult.is_match ? 'Verified Same Person' : 'Different Identity'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
