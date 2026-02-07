"use client";

import { useCallback, useRef, useState } from "react";

const API_BASE = "";
const ACCEPTED = ".mp3,.wav,.m4a,.ogg,.flac,.webm";
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

    console.log(`[upload] Upload initiated: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`);

    try {
      const form = new FormData();
      form.append("file", file);
      console.log("[upload] Sending fetch request...");
      const res = await fetch(`${API_BASE}/api/upload`, {
        method: "POST",
        body: form,
      });

      if (!res.ok) {
        const data = await res.json();
        console.error(`[upload] Upload failed: ${res.status}`, data);
        throw new Error(data.detail || "Upload failed");
      }

      const { job_id } = await res.json();
      console.log(`[upload] Response received: 200, job_id=${job_id}`);
      onJobCreated(job_id);
    } catch (err) {
      console.error("[upload] Error caught:", err);
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
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
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
          dragging
            ? "border-blue-500 bg-blue-50 dark:bg-blue-950"
            : "border-zinc-300 dark:border-zinc-700 hover:border-zinc-400 dark:hover:border-zinc-600"
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
          MP3, WAV, M4A, OGG, FLAC, WebM — max {MAX_SIZE_MB}MB
        </p>
      </div>

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
            {uploading ? "Uploading..." : "Upload & Process"}
          </button>
        </div>
      )}

      {error && (
        <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>
      )}
    </div>
  );
}
