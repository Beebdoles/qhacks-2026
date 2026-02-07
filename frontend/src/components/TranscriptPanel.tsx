"use client";

import { JobData } from "@/hooks/useJobPolling";

interface Props {
  job: JobData;
}

export default function TranscriptPanel({ job }: Props) {
  const transcriptions = job.transcriptions;
  if (transcriptions.length === 0) return null;

  return (
    <div className="w-full max-w-2xl mx-auto">
      <h3 className="text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-2">
        Speech Transcriptions
      </h3>
      <div className="space-y-2">
        {transcriptions.map((t, i) => (
          <div
            key={i}
            className="bg-zinc-50 dark:bg-zinc-800 rounded-lg px-4 py-3"
          >
            <span className="text-xs text-zinc-400 font-mono">
              {t.start.toFixed(1)}s — {t.end.toFixed(1)}s
            </span>
            <p className="mt-1 text-sm text-zinc-800 dark:text-zinc-200">
              {t.text}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
