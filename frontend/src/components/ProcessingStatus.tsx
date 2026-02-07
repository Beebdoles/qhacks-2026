"use client";

import { JobData } from "@/hooks/useJobPolling";

const STEP_LABELS: Record<string, string> = {
  "10": "Preprocessing audio...",
  "25": "Detecting speech segments...",
  "40": "Classifying audio segments...",
  "55": "Transcribing speech...",
  "70": "Extracting melody...",
  "85": "Detecting drum hits...",
  "95": "Assembling MIDI file...",
  "100": "Done!",
};

function getStepLabel(progress: number): string {
  const thresholds = [10, 25, 40, 55, 70, 85, 95, 100];
  for (const t of thresholds) {
    if (progress <= t) return STEP_LABELS[String(t)];
  }
  return "Processing...";
}

interface Props {
  job: JobData;
}

export default function ProcessingStatus({ job }: Props) {
  if (job.status === "failed") {
    return (
      <div className="w-full max-w-lg mx-auto bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-xl p-6">
        <p className="text-red-700 dark:text-red-400 font-medium">
          Processing failed
        </p>
        {job.error && (
          <p className="mt-2 text-sm text-red-600 dark:text-red-500 font-mono whitespace-pre-wrap">
            {job.error.split("\n")[0]}
          </p>
        )}
      </div>
    );
  }

  const label = getStepLabel(job.progress);

  return (
    <div className="w-full max-w-lg mx-auto">
      <div className="flex items-center gap-3 mb-3">
        {job.status !== "complete" && (
          <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
        )}
        <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          {label}
        </p>
      </div>
      <div className="w-full bg-zinc-200 dark:bg-zinc-700 rounded-full h-3 overflow-hidden">
        <div
          className="bg-blue-600 h-full rounded-full transition-all duration-500"
          style={{ width: `${job.progress}%` }}
        />
      </div>
      <p className="mt-2 text-xs text-zinc-400">{job.progress}%</p>
    </div>
  );
}
