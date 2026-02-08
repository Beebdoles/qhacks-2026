"use client";

import { useEditorStore } from "@/stores/editorStore";
import { PIPELINE_STAGES } from "@/lib/constants";

export default function EditProgressToast() {
  const jobProgress = useEditorStore((s) => s.jobProgress);
  const jobStage = useEditorStore((s) => s.jobStage);

  const stageLabel = PIPELINE_STAGES[jobStage] ?? jobStage;

  return (
    <div className="absolute bottom-4 right-4 bg-surface-800 border border-border rounded-lg p-4 shadow-lg z-20 min-w-[220px]">
      <div className="flex items-center gap-3">
        <svg className="animate-spin h-5 w-5 text-accent flex-shrink-0" viewBox="0 0 24 24">
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
        <div className="flex-1">
          <p className="text-sm text-text-primary">{stageLabel}</p>
          <div className="w-full h-1 bg-surface-600 rounded-full mt-1.5">
            <div
              className="h-full bg-accent rounded-full transition-all duration-300"
              style={{ width: `${jobProgress}%` }}
            />
          </div>
        </div>
        <span className="text-xs text-text-tertiary font-mono">{jobProgress}%</span>
      </div>
    </div>
  );
}
