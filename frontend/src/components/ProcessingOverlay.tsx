"use client";

import { useEffect } from "react";
import { useEditorStore } from "@/stores/editorStore";
import { useJobPolling } from "@/hooks/useJobPolling";
import { PIPELINE_STAGES } from "@/lib/constants";

export default function ProcessingOverlay() {
  const jobId = useEditorStore((s) => s.jobId);
  const jobProgress = useEditorStore((s) => s.jobProgress);
  const jobStage = useEditorStore((s) => s.jobStage);
  const setJobProgress = useEditorStore((s) => s.setJobProgress);
  const setPhase = useEditorStore((s) => s.setPhase);

  const job = useJobPolling(jobId);

  useEffect(() => {
    if (!job) return;
    setJobProgress(job.progress, job.stage);

    if (job.status === "complete") {
      setPhase("editor");
    } else if (job.status === "failed") {
      setPhase("empty");
    }
  }, [job, setJobProgress, setPhase]);

  const stageLabel = PIPELINE_STAGES[jobStage] ?? jobStage;

  return (
    <div className="absolute inset-0 bg-surface-900/90 flex flex-col items-center justify-center z-10 backdrop-blur-sm">
      {/* Spinner */}
      <div className="relative mb-6">
        <svg className="animate-spin h-12 w-12 text-accent" viewBox="0 0 24 24">
          <circle
            className="opacity-25"
            cx="12" cy="12" r="10"
            stroke="currentColor" strokeWidth="3" fill="none"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
      </div>

      {/* Progress */}
      <p className="text-2xl font-semibold text-text-primary mb-2">
        {jobProgress}%
      </p>

      {/* Stage label */}
      <p className="text-sm text-text-secondary">
        {stageLabel}
      </p>

      {/* Progress bar */}
      <div className="w-48 h-1 bg-surface-600 rounded-full mt-4 overflow-hidden">
        <div
          className="h-full bg-accent rounded-full transition-all duration-300"
          style={{ width: `${jobProgress}%` }}
        />
      </div>
    </div>
  );
}
