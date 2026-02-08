import { create } from "zustand";
import type { AppPhase, TrackState, ViewportState, TransportState } from "@/types/editor";

interface EditorState {
  // App phase
  phase: AppPhase;
  setPhase: (phase: AppPhase) => void;

  // Job tracking
  jobId: string | null;
  setJobId: (id: string | null) => void;
  jobProgress: number;
  jobStage: string;
  setJobProgress: (progress: number, stage: string) => void;

  // Tracks
  tracks: TrackState[];
  setTracks: (tracks: TrackState[]) => void;
  toggleMute: (index: number) => void;
  toggleVisible: (index: number) => void;
  renameTrack: (index: number, newName: string, newFilename: string) => void;

  // Transport
  transport: TransportState;
  setPlaying: (playing: boolean) => void;
  setCurrentTime: (time: number) => void;
  setBpm: (bpm: number) => void;
  setTimeSignature: (ts: [number, number]) => void;

  // Viewport
  viewport: ViewportState;
  setScrollX: (x: number) => void;
  setPixelsPerSecond: (pps: number) => void;
  setTotalDuration: (d: number) => void;

  // Recorded audio file (for upload)
  recordedFile: File | null;
  setRecordedFile: (f: File | null) => void;

  // Edit mode (voice command in editor)
  isEditing: boolean;
  setIsEditing: (editing: boolean) => void;
  editGeneration: number;
  bumpEditGeneration: () => void;

  // Error modal
  errorMessage: string | null;
  setErrorMessage: (msg: string | null) => void;
}

export const useEditorStore = create<EditorState>((set) => ({
  phase: "empty",
  setPhase: (phase) => set({ phase }),

  jobId: null,
  setJobId: (jobId) => set({ jobId }),
  jobProgress: 0,
  jobStage: "",
  setJobProgress: (jobProgress, jobStage) => set({ jobProgress, jobStage }),

  tracks: [],
  setTracks: (tracks) => set({ tracks }),
  toggleMute: (index) =>
    set((s) => ({
      tracks: s.tracks.map((t) =>
        t.index === index ? { ...t, muted: !t.muted } : t
      ),
    })),
  toggleVisible: (index) =>
    set((s) => ({
      tracks: s.tracks.map((t) =>
        t.index === index ? { ...t, visible: !t.visible } : t
      ),
    })),
  renameTrack: (index, newName, newFilename) =>
    set((s) => ({
      tracks: s.tracks.map((t) =>
        t.index === index ? { ...t, name: newName, filename: newFilename } : t
      ),
    })),

  transport: { playing: false, currentTime: 0, bpm: 120, timeSignature: [4, 4] },
  setPlaying: (playing) =>
    set((s) => ({ transport: { ...s.transport, playing } })),
  setCurrentTime: (currentTime) =>
    set((s) => ({ transport: { ...s.transport, currentTime } })),
  setBpm: (bpm) =>
    set((s) => ({ transport: { ...s.transport, bpm } })),
  setTimeSignature: (timeSignature) =>
    set((s) => ({ transport: { ...s.transport, timeSignature } })),

  viewport: { scrollX: 0, pixelsPerSecond: 100, totalDuration: 0 },
  setScrollX: (scrollX) =>
    set((s) => ({ viewport: { ...s.viewport, scrollX } })),
  setPixelsPerSecond: (pixelsPerSecond) =>
    set((s) => ({ viewport: { ...s.viewport, pixelsPerSecond } })),
  setTotalDuration: (totalDuration) =>
    set((s) => ({ viewport: { ...s.viewport, totalDuration } })),

  recordedFile: null,
  setRecordedFile: (recordedFile) => set({ recordedFile }),

  isEditing: false,
  setIsEditing: (isEditing) => set({ isEditing }),
  editGeneration: 0,
  bumpEditGeneration: () => set((s) => ({ editGeneration: s.editGeneration + 1 })),

  errorMessage: null,
  setErrorMessage: (errorMessage) => set({ errorMessage }),
}));
