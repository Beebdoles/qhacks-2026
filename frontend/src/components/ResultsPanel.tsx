"use client";

import { JobData } from "@/hooks/useJobPolling";

const API_BASE = "http://localhost:8000";

interface Props {
  job: JobData;
}

export default function ResultsPanel({ job }: Props) {
  if (job.status !== "complete") return null;

  const speechCount = job.segments.filter((s) => s.type === "speech").length;
  const hummingCount = job.segments.filter((s) => s.type === "humming").length;
  const beatboxCount = job.segments.filter(
    (s) => s.type === "beatboxing"
  ).length;

  return (
    <div className="w-full max-w-2xl mx-auto">
      <h3 className="text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-3">
        Results
      </h3>

      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-blue-50 dark:bg-blue-950 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-blue-600">{speechCount}</p>
          <p className="text-xs text-blue-500">Speech segments</p>
        </div>
        <div className="bg-green-50 dark:bg-green-950 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-green-600">{hummingCount}</p>
          <p className="text-xs text-green-500">Humming segments</p>
        </div>
        <div className="bg-orange-50 dark:bg-orange-950 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-orange-600">{beatboxCount}</p>
          <p className="text-xs text-orange-500">Beatbox segments</p>
        </div>
      </div>

      <a
        href={`${API_BASE}/api/jobs/${job.id}/midi`}
        download="output.mid"
        className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors"
      >
        <span>Download MIDI</span>
      </a>
    </div>
  );
}
