"use client";

import { useRef, useEffect, useCallback } from "react";
import { useEditorStore } from "@/stores/editorStore";
import { drawGrid } from "./GridLayer";
import { drawNotes } from "./NoteLayer";
import { drawPlayhead } from "./PlayheadLayer";
import { PIANO_ROLL_HEIGHT } from "@/lib/constants";

interface TrackCanvasProps {
  onSeek?: (time: number) => void;
}

export default function TrackCanvas({ onSeek }: TrackCanvasProps) {
  const gridRef = useRef<HTMLCanvasElement>(null);
  const noteRef = useRef<HTMLCanvasElement>(null);
  const playheadRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number | null>(null);

  const tracks = useEditorStore((s) => s.tracks);
  const transport = useEditorStore((s) => s.transport);
  const viewport = useEditorStore((s) => s.viewport);

  const setupCanvas = useCallback((canvas: HTMLCanvasElement, width: number, height: number) => {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    const ctx = canvas.getContext("2d")!;
    ctx.scale(dpr, dpr);
    return ctx;
  }, []);

  // Resize observer
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver(() => {
      redrawGridAndNotes();
    });

    observer.observe(container);
    return () => observer.disconnect();
  });

  const redrawGridAndNotes = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth;
    const height = PIANO_ROLL_HEIGHT;

    if (gridRef.current) {
      const ctx = setupCanvas(gridRef.current, width, height);
      drawGrid({
        ctx,
        width,
        height,
        scrollX: viewport.scrollX,
        pixelsPerSecond: viewport.pixelsPerSecond,
        bpm: transport.bpm,
        timeSignature: transport.timeSignature,
      });
    }

    if (noteRef.current) {
      const ctx = setupCanvas(noteRef.current, width, height);
      drawNotes({
        ctx,
        width,
        height,
        scrollX: viewport.scrollX,
        pixelsPerSecond: viewport.pixelsPerSecond,
        tracks,
      });
    }
  }, [tracks, viewport.scrollX, viewport.pixelsPerSecond, transport.bpm, transport.timeSignature, setupCanvas]);

  // Redraw grid & notes when deps change
  useEffect(() => {
    redrawGridAndNotes();
  }, [redrawGridAndNotes]);

  // Playhead animation loop
  useEffect(() => {
    const animate = () => {
      const container = containerRef.current;
      const canvas = playheadRef.current;
      if (!container || !canvas) return;

      const width = container.clientWidth;
      const height = PIANO_ROLL_HEIGHT;
      const ctx = setupCanvas(canvas, width, height);

      const { transport: t, viewport: v } = useEditorStore.getState();

      drawPlayhead({
        ctx,
        width,
        height,
        scrollX: v.scrollX,
        pixelsPerSecond: v.pixelsPerSecond,
        currentTime: t.currentTime,
      });

      rafRef.current = requestAnimationFrame(animate);
    };

    rafRef.current = requestAnimationFrame(animate);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [setupCanvas]);

  // Click to seek
  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const container = containerRef.current;
      if (!container || !onSeek) return;

      const rect = container.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const time = (clickX + viewport.scrollX) / viewport.pixelsPerSecond;
      onSeek(Math.max(0, time));
    },
    [viewport.scrollX, viewport.pixelsPerSecond, onSeek]
  );

  return (
    <div
      ref={containerRef}
      className="relative w-full overflow-y-auto bg-surface-900 cursor-crosshair"
      style={{ height: "100%" }}
      onClick={handleClick}
    >
      <div style={{ position: "relative", width: "100%", height: PIANO_ROLL_HEIGHT }}>
        <canvas ref={gridRef} className="absolute inset-0" style={{ zIndex: 1 }} />
        <canvas ref={noteRef} className="absolute inset-0" style={{ zIndex: 2 }} />
        <canvas ref={playheadRef} className="absolute inset-0" style={{ zIndex: 3, pointerEvents: "none" }} />
      </div>
    </div>
  );
}
