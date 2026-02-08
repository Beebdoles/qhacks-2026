"use client";

import { useEditorStore } from "@/stores/editorStore";
import { formatTime } from "@/lib/midi-utils";

interface ToolbarProps {
  onPlay: () => void;
  onStop: () => void;
  onExport: () => void;
}

export default function Toolbar({ onPlay, onStop, onExport }: ToolbarProps) {
  const transport = useEditorStore((s) => s.transport);
  const phase = useEditorStore((s) => s.phase);

  const isEditor = phase === "editor";

  return (
    <div
      className="flex items-center px-4 bg-surface-800 border-b border-border"
      style={{ height: "var(--toolbar-height)" }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 min-w-[160px]">
        <div className="w-6 h-6 rounded bg-accent flex items-center justify-center">
          <span className="text-white text-xs font-bold">O</span>
        </div>
        <span className="text-sm font-semibold text-text-primary">Orca</span>
        <span className="text-xs text-text-tertiary ml-1">MIDI Editor</span>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Time display */}
      <div className="flex items-center gap-4">
        <span className="font-mono text-sm text-text-secondary tabular-nums">
          {formatTime(transport.currentTime)}
        </span>

        {/* Transport controls */}
        <div className="flex items-center gap-1">
          {/* Play/Pause */}
          <button
            onClick={onPlay}
            disabled={!isEditor}
            className="p-2 hover:bg-surface-600 rounded transition-all duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
            title={transport.playing ? "Pause" : "Play"}
          >
            {transport.playing ? (
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <rect x="3" y="2" width="4" height="12" rx="1" fill="white"/>
                <rect x="9" y="2" width="4" height="12" rx="1" fill="white"/>
              </svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <path d="M4 2.5a.5.5 0 0 1 .772-.42l9 6a.5.5 0 0 1 0 .84l-9 6A.5.5 0 0 1 4 14.5v-12Z" fill="white"/>
              </svg>
            )}
          </button>

          {/* Stop */}
          <button
            onClick={onStop}
            disabled={!isEditor}
            className="p-2 hover:bg-surface-600 rounded transition-all duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
            title="Stop"
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <rect x="3" y="3" width="10" height="10" rx="1" fill="white"/>
            </svg>
          </button>
        </div>

        {/* BPM / Time Signature */}
        <div className="flex items-center gap-2 text-xs text-text-tertiary">
          <span className="font-mono">{transport.bpm} BPM</span>
          <span>·</span>
          <span className="font-mono">{transport.timeSignature[0]}/{transport.timeSignature[1]}</span>
        </div>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Export */}
      <button
        onClick={onExport}
        disabled={!isEditor}
        className="px-3 py-1.5 bg-surface-600 hover:bg-surface-500 text-text-secondary text-xs font-medium rounded transition-all duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
      >
        Export .mid
      </button>
    </div>
  );
}
