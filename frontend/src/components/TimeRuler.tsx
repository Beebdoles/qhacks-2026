"use client";

import { useRef, useEffect, useCallback } from "react";
import { useEditorStore } from "@/stores/editorStore";

export default function TimeRuler() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const viewport = useEditorStore((s) => s.viewport);
  const transport = useEditorStore((s) => s.transport);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const width = container.clientWidth;
    const height = 32;
    const dpr = window.devicePixelRatio || 1;

    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext("2d")!;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    const { scrollX, pixelsPerSecond } = viewport;
    const { bpm, timeSignature } = transport;

    const secondsPerBeat = 60 / bpm;
    const secondsPerBar = secondsPerBeat * timeSignature[0];
    const pixelsPerBar = secondsPerBar * pixelsPerSecond;

    const startTime = scrollX / pixelsPerSecond;
    const endTime = (scrollX + width) / pixelsPerSecond;
    const firstBar = Math.floor(startTime / secondsPerBar);
    const lastBar = Math.ceil(endTime / secondsPerBar);

    ctx.fillStyle = "#A0A0A0";
    ctx.font = "10px 'IBM Plex Mono', monospace";
    ctx.textAlign = "left";

    for (let bar = firstBar; bar <= lastBar; bar++) {
      const barTime = bar * secondsPerBar;
      const x = barTime * pixelsPerSecond - scrollX;

      // Bar number
      if (bar >= 0) {
        ctx.fillStyle = "#A0A0A0";
        ctx.fillText(`${bar + 1}`, x + 4, 14);
      }

      // Tick mark
      ctx.strokeStyle = "#3A3A3A";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, 20);
      ctx.lineTo(x, height);
      ctx.stroke();

      // Beat ticks
      for (let beat = 1; beat < timeSignature[0]; beat++) {
        const beatX = x + (beat / timeSignature[0]) * pixelsPerBar;
        ctx.strokeStyle = "#2E2E2E";
        ctx.lineWidth = 0.5;
        ctx.beginPath();
        ctx.moveTo(beatX, 24);
        ctx.lineTo(beatX, height);
        ctx.stroke();
      }
    }
  }, [viewport, transport]);

  useEffect(() => {
    draw();
  }, [draw]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const observer = new ResizeObserver(() => draw());
    observer.observe(container);
    return () => observer.disconnect();
  }, [draw]);

  return (
    <div
      ref={containerRef}
      className="bg-surface-800 border-b border-border"
      style={{ height: "var(--ruler-height)" }}
    >
      <canvas ref={canvasRef} />
    </div>
  );
}
