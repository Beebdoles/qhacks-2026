"use client";

import { useEditorStore } from "@/stores/editorStore";

export default function StatusBar() {
  const tracks = useEditorStore((s) => s.tracks);
  const viewport = useEditorStore((s) => s.viewport);

  const totalNotes = tracks.reduce((sum, t) => sum + t.notes.length, 0);
  const zoom = Math.round((viewport.pixelsPerSecond / 100) * 100);

  return (
    <div
      className="flex items-center px-4 bg-surface-800 border-t border-border text-xs text-text-tertiary gap-4"
      style={{ height: "var(--statusbar-height)" }}
    >
      <span>Snap: 1/16</span>
      <span>Key: C Major</span>
      <span>Quantize: Off</span>
      <div className="flex-1" />
      <span>Zoom: {zoom}%</span>
      <span>{totalNotes} notes</span>
    </div>
  );
}
