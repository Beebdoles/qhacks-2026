"use client";

import { useRef, useCallback } from "react";
import { useEditorStore } from "@/stores/editorStore";
import TimeRuler from "./TimeRuler";
import TrackCanvas from "./canvas/TrackCanvas";
import ProcessingOverlay from "./ProcessingOverlay";

interface TimelineAreaProps {
  onSeek: (time: number) => void;
}

export default function TimelineArea({ onSeek }: TimelineAreaProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const phase = useEditorStore((s) => s.phase);
  const viewport = useEditorStore((s) => s.viewport);
  const setScrollX = useEditorStore((s) => s.setScrollX);

  const handleScroll = useCallback(() => {
    if (scrollRef.current) {
      setScrollX(scrollRef.current.scrollLeft);
    }
  }, [setScrollX]);

  const totalWidth = viewport.totalDuration * viewport.pixelsPerSecond;

  return (
    <div className="flex-1 flex flex-col relative overflow-hidden">
      {/* Ruler */}
      <TimeRuler />

      {/* Canvas area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-x-auto overflow-y-auto"
        onScroll={handleScroll}
      >
        <div style={{ minWidth: Math.max(totalWidth, 1000) }}>
          <TrackCanvas onSeek={onSeek} />
        </div>
      </div>

      {/* Processing overlay */}
      {phase === "processing" && <ProcessingOverlay />}
    </div>
  );
}
