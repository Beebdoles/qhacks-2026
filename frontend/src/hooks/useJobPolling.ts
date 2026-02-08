import { useEffect, useRef, useState } from "react";

interface Segment {
  start: number;
  end: number;
  type: string;
}

export interface JobData {
  id: string;
  status: "pending" | "processing" | "complete" | "failed";
  progress: number;
  stage: string;
  segments: Segment[];
  midi_path: string | null;
  instruction_doc: string | null;
  action_log: Record<string, unknown>[];
  error: string | null;
}

const API_BASE = "";

export function useJobPolling(jobId: string | null, generation: number = 0) {
  const [data, setData] = useState<JobData | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!jobId) {
      setData(null);
      return;
    }

    console.log(`[polling] Started polling for job ${jobId.slice(0, 8)} (gen=${generation})`);

    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
        if (res.ok) {
          const json: JobData = await res.json();
          console.log(`[polling] Job ${jobId.slice(0, 8)}: status=${json.status}, progress=${json.progress}%`);
          setData(json);
          if (json.status === "complete" || json.status === "failed") {
            console.log(`[polling] Stopped polling for job ${jobId.slice(0, 8)}: ${json.status}`);
            if (intervalRef.current) {
              clearInterval(intervalRef.current);
              intervalRef.current = null;
            }
          }
        }
      } catch {
        // Network error — keep polling
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 2000);

    return () => {
      if (intervalRef.current) {
        console.log(`[polling] Cleanup: stopped polling for job ${jobId.slice(0, 8)}`);
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [jobId, generation]);

  return data;
}
