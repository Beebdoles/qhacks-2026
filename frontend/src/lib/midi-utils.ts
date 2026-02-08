import { Midi } from "@tonejs/midi";
import type { NoteEvent, TrackState } from "@/types/editor";
import { TRACK_COLORS, GM_INSTRUMENTS } from "@/lib/constants";

export async function fetchMidiAsArrayBuffer(url: string): Promise<ArrayBuffer> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch MIDI: ${res.status}`);
  return res.arrayBuffer();
}

export function parseMidiToTracks(arrayBuffer: ArrayBuffer): {
  tracks: TrackState[];
  duration: number;
  bpm: number;
  timeSignature: [number, number];
} {
  const midi = new Midi(arrayBuffer);

  const bpm = midi.header.tempos.length > 0 ? Math.round(midi.header.tempos[0].bpm) : 120;
  const ts = midi.header.timeSignatures.length > 0
    ? [midi.header.timeSignatures[0].timeSignature[0], midi.header.timeSignatures[0].timeSignature[1]] as [number, number]
    : [4, 4] as [number, number];

  let duration = 0;

  const tracks: TrackState[] = midi.tracks
    .map((track, i): TrackState | null => {
      if (track.notes.length === 0) return null;

      const channel = track.channel ?? 0;
      const programNumber = track.instrument?.number ?? 0;
      const instrument = channel === 9
        ? "Percussion"
        : GM_INSTRUMENTS[programNumber] ?? `Program ${programNumber}`;
      const name = track.name || instrument;

      const notes: NoteEvent[] = track.notes.map((n) => {
        const endTime = n.time + n.duration;
        if (endTime > duration) duration = endTime;
        return {
          midi: n.midi,
          name: n.name,
          time: n.time,
          duration: n.duration,
          velocity: n.velocity,
        };
      });

      return {
        index: i,
        name,
        instrument,
        programNumber,
        channel,
        notes,
        color: TRACK_COLORS[i % TRACK_COLORS.length],
        muted: false,
        visible: true,
      };
    })
    .filter((t): t is TrackState => t !== null);

  // Re-index filtered tracks
  tracks.forEach((t, i) => { t.index = i; t.color = TRACK_COLORS[i % TRACK_COLORS.length]; });

  return { tracks, duration, bpm, timeSignature: ts };
}

interface SavedTrackEntry {
  filename: string;
  url: string;
}

export async function loadAllSavedTracks(): Promise<{
  tracks: TrackState[];
  duration: number;
  bpm: number;
  timeSignature: [number, number];
}> {
  const res = await fetch("/api/tracks");
  if (!res.ok) throw new Error(`Failed to list tracks: ${res.status}`);
  const entries: SavedTrackEntry[] = await res.json();

  if (entries.length === 0) {
    return { tracks: [], duration: 0, bpm: 120, timeSignature: [4, 4] };
  }

  const allTracks: TrackState[] = [];
  let maxDuration = 0;
  let bpm = 120;
  let timeSignature: [number, number] = [4, 4];

  for (const entry of entries) {
    const arrayBuffer = await fetchMidiAsArrayBuffer(entry.url);
    const parsed = parseMidiToTracks(arrayBuffer);

    // Use BPM/time sig from the first file that has notes
    if (parsed.tracks.length > 0 && allTracks.length === 0) {
      bpm = parsed.bpm;
      timeSignature = parsed.timeSignature;
    }

    if (parsed.duration > maxDuration) maxDuration = parsed.duration;

    // Use the filename (without .mid) as the track name
    const baseName = entry.filename.replace(/\.mid$/i, "").replace(/_/g, " ");
    for (const track of parsed.tracks) {
      track.name = baseName;
      allTracks.push(track);
    }
  }

  // Re-index and re-color all combined tracks
  allTracks.forEach((t, i) => {
    t.index = i;
    t.color = TRACK_COLORS[i % TRACK_COLORS.length];
  });

  return { tracks: allTracks, duration: maxDuration, bpm, timeSignature };
}

export function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 100);
  return `${m}:${s.toString().padStart(2, "0")}.${ms.toString().padStart(2, "0")}`;
}
