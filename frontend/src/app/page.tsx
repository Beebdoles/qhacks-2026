"use client";

import { useState } from "react";
import AudioUpload from "@/components/AudioUpload";
import ProcessingStatus from "@/components/ProcessingStatus";
import SegmentTimeline from "@/components/SegmentTimeline";
import { useJobPolling } from "@/hooks/useJobPolling";

export default function Home() {
  const [jobId, setJobId] = useState<string | null>(null);
  const job = useJobPolling(jobId);

  const phase =
    !jobId || !job
      ? "upload"
      : job.status === "complete"
        ? "results"
        : "processing";

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black font-sans">
      <header className="border-b border-zinc-200 dark:border-zinc-800">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold text-zinc-900 dark:text-white">
            Audio Segment Analyzer
          </h1>
          {jobId && (
            <button
              onClick={() => setJobId(null)}
              className="text-sm text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 transition-colors"
            >
              New Upload
            </button>
          )}
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-12 space-y-8">
        {phase === "upload" && (
          <>
            <div className="text-center mb-8">
              <h2 className="text-3xl font-bold text-zinc-900 dark:text-white mb-2">
                Upload your audio
              </h2>
              <p className="text-zinc-500">
                Upload an MP3 file or record audio, and we&apos;ll classify the segments.
              </p>
            </div>
            <AudioUpload onJobCreated={setJobId} />
          </>
        )}

        {phase === "processing" && job && (
          <>
            <ProcessingStatus job={job} />
            <SegmentTimeline job={job} />
          </>
        )}

        {phase === "results" && job && (
          <>
            <div className="text-center mb-4">
              <h2 className="text-2xl font-bold text-zinc-900 dark:text-white">
                Analysis Complete
              </h2>
            </div>
            <SegmentTimeline job={job} />
          </>
        )}
      </main>
    </div>
  );
}
