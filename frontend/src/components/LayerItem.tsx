"use client";

import { useEditorStore } from "@/stores/editorStore";
import type { TrackState } from "@/types/editor";

interface LayerItemProps {
  track: TrackState;
}

export default function LayerItem({ track }: LayerItemProps) {
  const toggleMute = useEditorStore((s) => s.toggleMute);
  const toggleVisible = useEditorStore((s) => s.toggleVisible);

  return (
    <div
      className={`flex items-center gap-2 px-3 py-2 border-b border-border transition-all duration-150 ${
        track.muted ? "opacity-40" : ""
      }`}
    >
      {/* Color indicator */}
      <div
        className="w-1 h-8 rounded-full flex-shrink-0"
        style={{ backgroundColor: track.color }}
      />

      {/* Name and instrument */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-text-primary truncate">{track.name}</p>
        <p className="text-xs text-text-tertiary truncate">{track.instrument}</p>
      </div>

      {/* Mute toggle */}
      <button
        onClick={() => toggleMute(track.index)}
        className="p-1 hover:bg-surface-600 rounded transition-all duration-150 cursor-pointer"
        title={track.muted ? "Unmute" : "Mute"}
      >
        {track.muted ? (
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-text-tertiary">
            <path d="M9 2.5a.5.5 0 0 0-.854-.354L4.793 5.5H2.5A1.5 1.5 0 0 0 1 7v2a1.5 1.5 0 0 0 1.5 1.5h2.293l3.353 3.354A.5.5 0 0 0 9 13.5v-11Z" fill="currentColor"/>
            <path d="M11.146 5.146a.5.5 0 0 1 .708 0L13 6.293l1.146-1.147a.5.5 0 0 1 .708.708L13.707 7l1.147 1.146a.5.5 0 0 1-.708.708L13 7.707l-1.146 1.147a.5.5 0 0 1-.708-.708L12.293 7l-1.147-1.146a.5.5 0 0 1 0-.708Z" fill="currentColor"/>
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-text-secondary">
            <path d="M9 2.5a.5.5 0 0 0-.854-.354L4.793 5.5H2.5A1.5 1.5 0 0 0 1 7v2a1.5 1.5 0 0 0 1.5 1.5h2.293l3.353 3.354A.5.5 0 0 0 9 13.5v-11Z" fill="currentColor"/>
            <path d="M11.5 4.5a.5.5 0 0 0-.354.854 5 5 0 0 1 0 5.292.5.5 0 0 0 .708.708 6 6 0 0 0 0-6.708.5.5 0 0 0-.354-.146Z" fill="currentColor"/>
            <path d="M10.5 6.5a.5.5 0 0 0-.354.854 2 2 0 0 1 0 1.292.5.5 0 0 0 .708.708 3 3 0 0 0 0-2.708.5.5 0 0 0-.354-.146Z" fill="currentColor"/>
          </svg>
        )}
      </button>

      {/* Visibility toggle */}
      <button
        onClick={() => toggleVisible(track.index)}
        className="p-1 hover:bg-surface-600 rounded transition-all duration-150 cursor-pointer"
        title={track.visible ? "Hide" : "Show"}
      >
        {track.visible ? (
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-text-secondary">
            <path d="M8 3C4.364 3 1.258 5.073.254 7.877a.5.5 0 0 0 0 .246C1.258 10.927 4.364 13 8 13s6.742-2.073 7.746-4.877a.5.5 0 0 0 0-.246C14.742 5.073 11.636 3 8 3Zm0 8a3 3 0 1 1 0-6 3 3 0 0 1 0 6Z" fill="currentColor"/>
            <circle cx="8" cy="8" r="1.5" fill="currentColor"/>
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-text-tertiary">
            <path d="M2.854 2.146a.5.5 0 1 0-.708.708l2.07 2.07C2.636 5.927 1.5 7.077 1.254 7.877a.5.5 0 0 0 0 .246c.87 2.44 3.317 4.21 6.246 4.36l2.646 2.647a.5.5 0 0 0 .708-.708l-8-8ZM8 11a3 3 0 0 1-2.83-4.024l1.36 1.36A1.5 1.5 0 0 0 8.464 10.3l1.322 1.32A3 3 0 0 1 8 11Z" fill="currentColor"/>
            <path d="M14.746 8.123c-.61 1.71-1.927 3.066-3.604 3.817l-1.189-1.19a3 3 0 0 0-3.703-3.703L5.187 5.985A7.69 7.69 0 0 1 8 5c3.636 0 6.742 2.073 7.746 4.877a.5.5 0 0 1 0 .246Z" fill="currentColor"/>
          </svg>
        )}
      </button>
    </div>
  );
}
