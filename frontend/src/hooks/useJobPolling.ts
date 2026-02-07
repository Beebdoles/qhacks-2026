import { useEffect, useRef, useState } from "react";

interface Segment {
  start: number;
  end: number;
  type: string;
}

interface Transcription {
  start: number;
  end: number;
  text: string;
}

export interface JobData {
  id: string;
  status: "pending" | "processing" | "complete" | "failed";
  progress: number;
  segments: Segment[];
  transcriptions: Transcription[];
  error: string | null;
}

const API_BASE = "http://localhost:8000";

export function useJobPolling(jobId: string | null) {
  const [data, setData] = useState<JobData | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!jobId) {
      setData(null);
      return;
    }

    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
        if (res.ok) {
          const json: JobData = await res.json();
          setData(json);
          if (json.status === "complete" || json.status === "failed") {
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
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [jobId]);

  return data;
}
