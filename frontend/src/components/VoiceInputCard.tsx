"use client";

import { useState, useCallback, useRef } from "react";
import { useAudioRecorder } from "@/hooks/useAudioRecorder";
import { useEditorStore } from "@/stores/editorStore";

type VoiceState = "ready" | "recording" | "review";

export default function VoiceInputCard() {
  const [voiceState, setVoiceState] = useState<VoiceState>("ready");
  const [recordedDuration, setRecordedDuration] = useState(0);
  const setPhase = useEditorStore((s) => s.setPhase);
  const setJobId = useEditorStore((s) => s.setJobId);
  const setRecordedFile = useEditorStore((s) => s.setRecordedFile);

  const handleRecordingComplete = useCallback((file: File) => {
    setRecordedFile(file);
    setVoiceState("review");
  }, [setRecordedFile]);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const { recorderState, elapsedSeconds, error, startRecording, stopRecording } =
    useAudioRecorder(handleRecordingComplete);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setRecordedFile(file);
    setRecordedDuration(0);
    setVoiceState("review");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleStart = () => {
    startRecording();
    setVoiceState("recording");
  };

  const handleStop = () => {
    setRecordedDuration(elapsedSeconds);
    stopRecording();
  };

  const handleDiscard = () => {
    setRecordedFile(null);
    setRecordedDuration(0);
    setVoiceState("ready");
  };

  const handleUpload = async () => {
    const file = useEditorStore.getState().recordedFile;
    if (!file) return;

    // Clear old jobId first so ProcessingOverlay doesn't poll a stale completed job
    setJobId(null);
    setPhase("processing");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/upload", { method: "POST", body: formData });
      if (!res.ok) throw new Error("Upload failed");
      const data = await res.json();
      setJobId(data.job_id);
    } catch (err) {
      console.error("Upload failed:", err);
      setPhase("empty");
      setVoiceState("ready");
    }
  };

  const formatDuration = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  return (
    <div className="bg-surface-700 rounded-lg p-4 mx-3 mb-3">
      {voiceState === "ready" && (
        <>
          <div className="flex items-center gap-2 mb-3">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="text-text-secondary">
              <path d="M8 1a2.5 2.5 0 0 0-2.5 2.5v4a2.5 2.5 0 0 0 5 0v-4A2.5 2.5 0 0 0 8 1Z" fill="currentColor"/>
              <path d="M4 6.5a.5.5 0 0 0-1 0v1a5 5 0 0 0 4.5 4.975V14H6a.5.5 0 0 0 0 1h4a.5.5 0 0 0 0-1H8.5v-1.525A5 5 0 0 0 13 7.5v-1a.5.5 0 0 0-1 0v1a4 4 0 0 1-8 0v-1Z" fill="currentColor"/>
            </svg>
            <span className="text-sm font-medium text-text-primary">Voice Input</span>
          </div>
          <p className="text-xs text-text-tertiary mb-3">Ready</p>
          {error && <p className="text-xs text-recording mb-2">{error}</p>}
          <div className="flex gap-2">
            <button
              onClick={handleStart}
              className="flex-1 py-2 px-3 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-md transition-all duration-150 cursor-pointer"
            >
              Record
            </button>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex-1 py-2 px-3 bg-surface-600 hover:brightness-90 text-text-secondary text-sm font-medium rounded-md transition-all duration-150 cursor-pointer"
            >
              Upload MP3
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".mp3,audio/mpeg"
            onChange={handleFileSelect}
            className="hidden"
          />
        </>
      )}

      {voiceState === "recording" && (
        <>
          <div className="flex items-center gap-2 mb-3">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-recording opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-recording"></span>
            </span>
            <span className="text-sm font-medium text-recording">Recording</span>
          </div>

          {/* Waveform animation */}
          <div className="flex items-center justify-center gap-[3px] h-8 mb-3">
            {[...Array(20)].map((_, i) => (
              <div
                key={i}
                className="w-[3px] bg-recording rounded-full"
                style={{
                  height: `${Math.random() * 24 + 8}px`,
                  animation: `waveform 0.5s ease-in-out ${i * 0.05}s infinite alternate`,
                }}
              />
            ))}
          </div>

          <p className="text-center text-lg font-mono text-text-primary mb-3">
            {formatDuration(elapsedSeconds)}
          </p>

          <button
            onClick={handleStop}
            className="w-full py-2 px-3 bg-recording hover:brightness-90 text-white text-sm font-medium rounded-md transition-all duration-150 cursor-pointer"
          >
            Stop Recording
          </button>
        </>
      )}

      {voiceState === "review" && (
        <>
          <div className="flex items-center gap-2 mb-3">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="text-success">
              <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1Zm3.354 5.354-4 4a.5.5 0 0 1-.708 0l-2-2a.5.5 0 1 1 .708-.708L7 9.293l3.646-3.647a.5.5 0 0 1 .708.708Z" fill="currentColor"/>
            </svg>
            <span className="text-sm font-medium text-text-primary">Recorded</span>
          </div>
          <p className="text-sm text-text-secondary mb-3">
            Duration: {formatDuration(recordedDuration)}
          </p>
          <div className="flex gap-2">
            <button
              onClick={handleDiscard}
              className="flex-1 py-2 px-3 bg-surface-600 hover:brightness-90 text-text-secondary text-sm font-medium rounded-md transition-all duration-150 cursor-pointer"
            >
              Discard
            </button>
            <button
              onClick={handleUpload}
              className="flex-1 py-2 px-3 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-md transition-all duration-150 cursor-pointer"
            >
              Upload
            </button>
          </div>
        </>
      )}

    </div>
  );
}
