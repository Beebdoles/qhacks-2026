"use client";

import { useState, useCallback, useRef } from "react";
import { useAudioRecorder } from "@/hooks/useAudioRecorder";
import { useEditorStore } from "@/stores/editorStore";

type CardState = "ready" | "recording" | "review" | "uploading" | "done";

export default function InstructionsCard() {
  const [cardState, setCardState] = useState<CardState>("ready");
  const [recordedFile, setRecordedFile] = useState<File | null>(null);
  const [recordedDuration, setRecordedDuration] = useState(0);
  const [savedFilename, setSavedFilename] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const jobId = useEditorStore((s) => s.jobId);
  const bumpMidiVersion = useEditorStore((s) => s.bumpMidiVersion);

  const handleRecordingComplete = useCallback((file: File) => {
    setRecordedFile(file);
    setCardState("review");
  }, []);

  const { elapsedSeconds, error, startRecording, stopRecording } =
    useAudioRecorder(handleRecordingComplete);

  const handleStart = () => {
    startRecording();
    setCardState("recording");
  };

  const handleStop = () => {
    setRecordedDuration(elapsedSeconds);
    stopRecording();
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setRecordedFile(file);
    setRecordedDuration(0);
    setCardState("review");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDiscard = () => {
    setRecordedFile(null);
    setRecordedDuration(0);
    setCardState("ready");
  };

  const handleUpload = async () => {
    if (!recordedFile || !jobId) return;
    setCardState("uploading");

    const formData = new FormData();
    formData.append("file", recordedFile);

    try {
      const res = await fetch(`/api/jobs/${jobId}/instructions`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Upload failed");
      const data = await res.json();
      setSavedFilename(data.filename);
      if (data.midi_updated) {
        bumpMidiVersion();
      }
      setCardState("done");
      // Reset after a few seconds
      setTimeout(() => {
        setCardState("ready");
        setRecordedFile(null);
        setSavedFilename(null);
      }, 3000);
    } catch (err) {
      console.error("Instruction upload failed:", err);
      setCardState("review");
    }
  };

  const formatDuration = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  return (
    <div className="bg-surface-700 rounded-lg p-3 mx-3 mb-3">
      <div className="flex items-center gap-2 mb-2">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-text-secondary">
          <path d="M8 1a2.5 2.5 0 0 0-2.5 2.5v4a2.5 2.5 0 0 0 5 0v-4A2.5 2.5 0 0 0 8 1Z" fill="currentColor"/>
          <path d="M4 6.5a.5.5 0 0 0-1 0v1a5 5 0 0 0 4.5 4.975V14H6a.5.5 0 0 0 0 1h4a.5.5 0 0 0 0-1H8.5v-1.525A5 5 0 0 0 13 7.5v-1a.5.5 0 0 0-1 0v1a4 4 0 0 1-8 0v-1Z" fill="currentColor"/>
        </svg>
        <span className="text-xs font-medium text-text-secondary">Instructions</span>
      </div>

      {cardState === "ready" && (
        <>
          {error && <p className="text-xs text-recording mb-2">{error}</p>}
          <div className="flex gap-2">
            <button
              onClick={handleStart}
              className="flex-1 py-1.5 px-2 bg-surface-600 hover:brightness-90 text-text-secondary text-xs font-medium rounded-md transition-all duration-150 cursor-pointer"
            >
              Record
            </button>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex-1 py-1.5 px-2 bg-surface-600 hover:brightness-90 text-text-secondary text-xs font-medium rounded-md transition-all duration-150 cursor-pointer"
            >
              Upload MP3
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".mp3,audio/mpeg,.webm,audio/webm"
            onChange={handleFileSelect}
            className="hidden"
          />
        </>
      )}

      {cardState === "recording" && (
        <>
          <div className="flex items-center gap-2 mb-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-recording opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-recording"></span>
            </span>
            <span className="text-xs text-recording">Recording</span>
            <span className="text-xs font-mono text-text-primary ml-auto">
              {formatDuration(elapsedSeconds)}
            </span>
          </div>
          <button
            onClick={handleStop}
            className="w-full py-1.5 px-2 bg-recording hover:brightness-90 text-white text-xs font-medium rounded-md transition-all duration-150 cursor-pointer"
          >
            Stop
          </button>
        </>
      )}

      {cardState === "review" && (
        <>
          <p className="text-xs text-text-secondary mb-2">
            {recordedDuration > 0
              ? `Recorded: ${formatDuration(recordedDuration)}`
              : `File: ${recordedFile?.name ?? ""}`}
          </p>
          <div className="flex gap-2">
            <button
              onClick={handleDiscard}
              className="flex-1 py-1.5 px-2 bg-surface-600 hover:brightness-90 text-text-secondary text-xs font-medium rounded-md transition-all duration-150 cursor-pointer"
            >
              Discard
            </button>
            <button
              onClick={handleUpload}
              className="flex-1 py-1.5 px-2 bg-accent hover:bg-accent-hover text-white text-xs font-medium rounded-md transition-all duration-150 cursor-pointer"
            >
              Save
            </button>
          </div>
        </>
      )}

      {cardState === "uploading" && (
        <p className="text-xs text-text-tertiary">Saving...</p>
      )}

      {cardState === "done" && (
        <p className="text-xs text-success">
          Saved as {savedFilename}
        </p>
      )}
    </div>
  );
}
