export type AppPhase = "empty" | "recording" | "review" | "processing" | "editor";

export interface NoteEvent {
  midi: number;        // MIDI note number 0-127
  name: string;        // e.g. "C4"
  time: number;        // start time in seconds
  duration: number;    // duration in seconds
  velocity: number;    // 0-1
}

export interface TrackState {
  index: number;
  name: string;
  instrument: string;
  programNumber: number;
  channel: number;
  notes: NoteEvent[];
  color: string;
  muted: boolean;
  visible: boolean;
}

export interface ViewportState {
  scrollX: number;
  pixelsPerSecond: number;
  totalDuration: number;
}

export interface TransportState {
  playing: boolean;
  currentTime: number;
  bpm: number;
  timeSignature: [number, number];
}
