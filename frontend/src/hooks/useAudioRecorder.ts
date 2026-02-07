import { useCallback, useEffect, useRef, useState } from "react";

type RecorderState = "idle" | "requesting" | "recording";

export interface UseAudioRecorderReturn {
  recorderState: RecorderState;
  elapsedSeconds: number;
  error: string | null;
  startRecording: () => void;
  stopRecording: () => void;
}

export function useAudioRecorder(
  onRecordingComplete: (file: File) => void
): UseAudioRecorderReturn {
  const [recorderState, setRecorderState] = useState<RecorderState>("idle");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onCompleteRef = useRef(onRecordingComplete);
  onCompleteRef.current = onRecordingComplete;

  const cleanup = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    mediaRecorderRef.current = null;
    chunksRef.current = [];
    setElapsedSeconds(0);
  }, []);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setRecorderState("idle");
  }, []);

  const startRecording = useCallback(() => {
    setError(null);
    setRecorderState("requesting");

    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((stream) => {
        streamRef.current = stream;
        chunksRef.current = [];

        const recorder = new MediaRecorder(stream);
        mediaRecorderRef.current = recorder;

        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) chunksRef.current.push(e.data);
        };

        recorder.onstop = () => {
          const blob = new Blob(chunksRef.current, { type: "audio/webm" });
          const timestamp = Date.now();
          const file = new File([blob], `recording-${timestamp}.webm`, {
            type: "audio/webm",
          });
          onCompleteRef.current(file);
          chunksRef.current = [];
        };

        recorder.start();
        setRecorderState("recording");
        setElapsedSeconds(0);
        timerRef.current = setInterval(() => {
          setElapsedSeconds((s) => s + 1);
        }, 1000);
      })
      .catch((err: DOMException) => {
        setRecorderState("idle");
        if (err.name === "NotAllowedError") {
          setError("Microphone access denied.");
        } else if (err.name === "NotFoundError") {
          setError("No microphone found.");
        } else {
          setError("Could not access microphone.");
        }
      });
  }, []);

  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  return { recorderState, elapsedSeconds, error, startRecording, stopRecording };
}
