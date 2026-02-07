"use client";

import { JobData } from "@/hooks/useJobPolling";

const SEGMENT_COLORS: Record<string, string> = {
  speech: "bg-blue-500",
  humming: "bg-green-500",
  beatboxing: "bg-orange-500",
  silence: "bg-zinc-300 dark:bg-zinc-600",
};

const SEGMENT_LABELS: Record<string, string> = {
  speech: "Speech",
  humming: "Humming",
  beatboxing: "Beatboxing",
  silence: "Silence",
};

interface Props {
  job: JobData;
}

export default function SegmentTimeline({ job }: Props) {
  const segments = job.segments;
  if (segments.length === 0) return null;

  const totalDuration = Math.max(...segments.map((s) => s.end));
  if (totalDuration <= 0) return null;

  return (
    <div className="w-full max-w-2xl mx-auto">
      <h3 className="text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-2">
        Audio Segments
      </h3>
      <div className="relative w-full h-10 bg-zinc-100 dark:bg-zinc-800 rounded-lg overflow-hidden">
        {segments.map((seg, i) => {
          const left = (seg.start / totalDuration) * 100;
          const width = ((seg.end - seg.start) / totalDuration) * 100;
          const color = SEGMENT_COLORS[seg.type] || SEGMENT_COLORS.silence;
          return (
            <div
              key={i}
              className={`absolute top-0 h-full ${color} opacity-80 hover:opacity-100 transition-opacity`}
              style={{ left: `${left}%`, width: `${Math.max(width, 0.5)}%` }}
              title={`${SEGMENT_LABELS[seg.type] || seg.type}: ${seg.start.toFixed(1)}s - ${seg.end.toFixed(1)}s`}
            />
          );
        })}
      </div>
      <div className="flex gap-4 mt-3">
        {Object.entries(SEGMENT_LABELS).map(([type, label]) => (
          <div key={type} className="flex items-center gap-1.5">
            <div
              className={`w-3 h-3 rounded-sm ${SEGMENT_COLORS[type]}`}
            />
            <span className="text-xs text-zinc-500">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
