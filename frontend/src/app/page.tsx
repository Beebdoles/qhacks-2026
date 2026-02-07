"use client";

import { useCallback, useEffect } from "react";
import { useEditorStore } from "@/stores/editorStore";
import { useAnimationFrame } from "@/hooks/useAnimationFrame";
import Toolbar from "@/components/Toolbar";
import LayerPanel from "@/components/LayerPanel";
import TimelineArea from "@/components/TimelineArea";
import StatusBar from "@/components/StatusBar";
import { audioEngine, setStoreGetter } from "@/lib/AudioEngine";
import { fetchMidiAsArrayBuffer, parseMidiToTracks } from "@/lib/midi-utils";

// Register store getter for AudioEngine (avoids circular import)
setStoreGetter(() => useEditorStore.getState());

export default function Home() {
  const phase = useEditorStore((s) => s.phase);
  const jobId = useEditorStore((s) => s.jobId);

  // Drive playhead animation
  useAnimationFrame();

  // When entering editor phase, fetch and load MIDI
  useEffect(() => {
    if (phase !== "editor" || !jobId) return;

    let cancelled = false;

    async function loadMidi() {
      try {
        const arrayBuffer = await fetchMidiAsArrayBuffer(`/api/jobs/${jobId}/midi`);
        if (cancelled) return;

        const { tracks, duration, bpm, timeSignature } = parseMidiToTracks(arrayBuffer);

        const store = useEditorStore.getState();
        store.setTracks(tracks);
        store.setBpm(bpm);
        store.setTimeSignature(timeSignature);
        store.setTotalDuration(duration);
        store.setCurrentTime(0);

        await audioEngine.loadTracks(tracks);
      } catch (err) {
        console.error("Failed to load MIDI:", err);
      }
    }

    loadMidi();
    return () => { cancelled = true; };
  }, [phase, jobId]);

  // Sync mute toggles with audio engine GainNodes
  useEffect(() => {
    const unsub = useEditorStore.subscribe((state) => {
      for (const track of state.tracks) {
        audioEngine.setTrackMute(track.index, track.muted);
      }
    });
    return unsub;
  }, []);

  // Auto-stop at end of MIDI
  useEffect(() => {
    audioEngine.onEnd(() => {
      useEditorStore.getState().setPlaying(false);
      useEditorStore.getState().setCurrentTime(0);
    });
  }, []);

  // Handle play/pause
  const handlePlay = useCallback(async () => {
    const store = useEditorStore.getState();
    if (store.phase !== "editor") return;

    await audioEngine.ensureStarted();

    if (store.transport.playing) {
      audioEngine.pause();
      store.setPlaying(false);
    } else {
      audioEngine.play(store.tracks, store.transport.currentTime);
      store.setPlaying(true);
    }
  }, []);

  // Handle stop
  const handleStop = useCallback(() => {
    audioEngine.stop();
    const store = useEditorStore.getState();
    store.setPlaying(false);
    store.setCurrentTime(0);
  }, []);

  // Handle seek
  const handleSeek = useCallback((time: number) => {
    const store = useEditorStore.getState();
    store.setCurrentTime(time);
    if (store.transport.playing) {
      audioEngine.seek(store.tracks, time);
    }
  }, []);

  // Handle export
  const handleExport = useCallback(() => {
    const store = useEditorStore.getState();
    if (!store.jobId) return;
    const url = `/api/jobs/${store.jobId}/midi`;
    const a = document.createElement("a");
    a.href = url;
    a.download = "output.mid";
    a.click();
  }, []);

  return (
    <div className="flex flex-col h-screen w-screen">
      {/* Toolbar */}
      <Toolbar onPlay={handlePlay} onStop={handleStop} onExport={handleExport} />

      {/* Main area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <LayerPanel />

        {/* Timeline */}
        <TimelineArea onSeek={handleSeek} />
      </div>

      {/* Status bar */}
      <StatusBar />
    </div>
  );
}
