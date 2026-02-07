"use client";

import { useCallback, useRef, useState } from "react";
import { useAudioRecorder } from "@/hooks/useAudioRecorder";

const API_BASE = "http://localhost:8000";
const ACCEPTED = ".mp3,.webm";
const MAX_SIZE_MB = 20;

interface Props {
  onJobCreated: (jobId: string) => void;
}

export default function AudioUpload({ onJobCreated }: Props) {
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback((f: File) => {
    setError(null);
    if (f.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`File too large. Max size: ${MAX_SIZE_MB}MB`);
      return;
    }
    setFile(f);
  }, []);

  const {
    recorderState,
    elapsedSeconds,
    error: recorderError,
    startRecording,
    stopRecording,
  } = useAudioRecorder(handleFile);

  const isRecording = recorderState !== "idle";

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const f = e.dataTransfer.files[0];
      if (f) handleFile(f);
    },
    [handleFile]
  );

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);

    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_BASE}/api/upload`, {
        method: "POST",
        body: form,
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Upload failed");
      }

      const { job_id } = await res.json();
      onJobCreated(job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="w-full max-w-lg mx-auto">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !isRecording && inputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors ${
          isRecording
            ? "opacity-50 pointer-events-none border-zinc-300 dark:border-zinc-700"
            : dragging
              ? "border-blue-500 bg-blue-50 dark:bg-blue-950 cursor-pointer"
              : "border-zinc-300 dark:border-zinc-700 hover:border-zinc-400 dark:hover:border-zinc-600 cursor-pointer"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
          }}
        />
        <div className="text-zinc-400 dark:text-zinc-500 text-4xl mb-3">
          ♪
        </div>
        <p className="text-zinc-600 dark:text-zinc-400 font-medium">
          Drop an audio file here or click to browse
        </p>
        <p className="text-xs text-zinc-400 dark:text-zinc-500 mt-2">
          MP3 or WebM — max {MAX_SIZE_MB}MB
        </p>
      </div>

      {!file && (
        <div className="mt-5">
          <div className="flex items-center gap-3 mb-5">
            <div className="flex-1 h-px bg-zinc-200 dark:bg-zinc-700" />
            <span className="text-xs text-zinc-400 dark:text-zinc-500">or</span>
            <div className="flex-1 h-px bg-zinc-200 dark:bg-zinc-700" />
          </div>

          {recorderState === "idle" && (
            <button
              onClick={startRecording}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg border border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
            >
              <span className="inline-block w-3 h-3 rounded-full bg-red-500" />
              Record Audio
            </button>
          )}

          {recorderState === "requesting" && (
            <p className="text-sm text-zinc-500 text-center py-3">
              Requesting microphone access...
            </p>
          )}

          {recorderState === "recording" && (
            <div className="flex items-center justify-center gap-4 py-3">
              <span className="inline-block w-3 h-3 rounded-full bg-red-500 animate-pulse" />
              <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300 tabular-nums">
                {formatTime(elapsedSeconds)}
              </span>
              <button
                onClick={stopRecording}
                className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 transition-colors"
              >
                Stop Recording
              </button>
            </div>
          )}
        </div>
      )}

      {file && (
        <div className="mt-4 flex items-center justify-between bg-zinc-100 dark:bg-zinc-800 rounded-lg px-4 py-3">
          <div className="min-w-0">
            <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200 truncate">
              {file.name}
            </p>
            <p className="text-xs text-zinc-500">
              {(file.size / (1024 * 1024)).toFixed(1)} MB
            </p>
          </div>
          <button
            onClick={handleUpload}
            disabled={uploading}
            className="ml-4 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {uploading ? "Uploading..." : "Upload & Analyze"}
          </button>
        </div>
      )}

      {(error || recorderError) && (
        <p className="mt-3 text-sm text-red-600 dark:text-red-400">
          {error || recorderError}
        </p>
      )}
    </div>
  );
}
