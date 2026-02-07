"use client";

import { useEditorStore } from "@/stores/editorStore";
import LayerItem from "./LayerItem";
import VoiceInputCard from "./VoiceInputCard";

export default function LayerPanel() {
  const tracks = useEditorStore((s) => s.tracks);
  const phase = useEditorStore((s) => s.phase);

  return (
    <div
      className="flex flex-col bg-surface-800 border-r border-border h-full"
      style={{ width: "var(--sidebar-width)" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
          Layers
        </span>
        <span className="text-xs text-text-tertiary">
          {tracks.length > 0 ? `${tracks.length} tracks` : ""}
        </span>
      </div>

      {/* Layer list */}
      <div className="flex-1 overflow-y-auto">
        {tracks.length === 0 && (
          <div className="px-3 py-8 text-center">
            <p className="text-xs text-text-tertiary">No tracks loaded</p>
          </div>
        )}
        {tracks.map((track) => (
          <LayerItem key={track.index} track={track} />
        ))}
      </div>

      {/* Voice input card — only show in empty/recording/review states */}
      {(phase === "empty" || phase === "recording" || phase === "review") && (
        <VoiceInputCard />
      )}
    </div>
  );
}
