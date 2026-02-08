"use client";

import { useCallback, useEffect } from "react";
import { useEditorStore } from "@/stores/editorStore";
import { useAnimationFrame } from "@/hooks/useAnimationFrame";
import { useJobPolling } from "@/hooks/useJobPolling";
import Toolbar from "@/components/Toolbar";
import LayerPanel from "@/components/LayerPanel";
import TimelineArea from "@/components/TimelineArea";
import StatusBar from "@/components/StatusBar";
import EditProgressToast from "@/components/EditProgressToast";
import EditErrorModal from "@/components/EditErrorModal";
import { audioEngine, setStoreGetter } from "@/lib/AudioEngine";
import { loadAllSavedTracks } from "@/lib/midi-utils";

// Register store getter for AudioEngine (avoids circular import)
setStoreGetter(() => useEditorStore.getState());

async function reloadTracks() {
  audioEngine.stop();
  useEditorStore.getState().setPlaying(false);

  const { tracks, duration, bpm, timeSignature } = await loadAllSavedTracks();

  const store = useEditorStore.getState();
  store.setTracks(tracks);
  store.setBpm(bpm);
  store.setTimeSignature(timeSignature);
  store.setTotalDuration(duration);
  store.setCurrentTime(0);

  await audioEngine.loadTracks(tracks);
}

export default function Home() {
  const phase = useEditorStore((s) => s.phase);
  const jobId = useEditorStore((s) => s.jobId);
  const isEditing = useEditorStore((s) => s.isEditing);
  const editGeneration = useEditorStore((s) => s.editGeneration);
  const errorMessage = useEditorStore((s) => s.errorMessage);
  const setErrorMessage = useEditorStore((s) => s.setErrorMessage);

  // Drive playhead animation
  useAnimationFrame();

  // Poll for edit pipeline progress (only when editing)
  const editJob = useJobPolling(isEditing ? jobId : null, editGeneration);

  // On startup, check if saved_tracks/ has files → go straight to editor
  useEffect(() => {
    if (phase !== "empty") return;

    let cancelled = false;

    async function checkSavedTracks() {
      try {
        const { tracks, duration, bpm, timeSignature } = await loadAllSavedTracks();
        if (cancelled || tracks.length === 0) return;

        const store = useEditorStore.getState();
        store.setTracks(tracks);
        store.setBpm(bpm);
        store.setTimeSignature(timeSignature);
        store.setTotalDuration(duration);
        store.setCurrentTime(0);
        store.setPhase("editor");

        await audioEngine.loadTracks(tracks);
      } catch (err) {
        console.error("Failed to check saved tracks:", err);
      }
    }

    checkSavedTracks();
    return () => { cancelled = true; };
  }, [phase]);

  // When entering editor phase (from pipeline), reload all saved tracks
  useEffect(() => {
    if (phase !== "editor") return;
    // Skip if tracks are already loaded (e.g. from startup check above)
    if (useEditorStore.getState().tracks.length > 0) return;

    let cancelled = false;

    async function loadTracks() {
      try {
        const { tracks, duration, bpm, timeSignature } = await loadAllSavedTracks();
        if (cancelled) return;

        const store = useEditorStore.getState();
        store.setTracks(tracks);
        store.setBpm(bpm);
        store.setTimeSignature(timeSignature);
        store.setTotalDuration(duration);
        store.setCurrentTime(0);

        await audioEngine.loadTracks(tracks);
      } catch (err) {
        console.error("Failed to load tracks:", err);
      }
    }

    loadTracks();
    return () => { cancelled = true; };
  }, [phase]);

  // Handle edit pipeline completion: reload MIDI when done
  useEffect(() => {
    if (!editJob || !isEditing) return;

    // Update progress in store for the toast overlay
    useEditorStore.getState().setJobProgress(editJob.progress, editJob.stage);

    if (editJob.status === "complete") {
      const hasActions = editJob.action_log && editJob.action_log.length > 0;

      if (!hasActions) {
        console.log("[edit] No tool calls produced — showing error modal");
        useEditorStore.getState().setIsEditing(false);
        setErrorMessage(
          "No valid instructions were found in your recording. Try speaking more clearly, e.g. \"Shift the pitch up by 5 semitones.\""
        );
        return;
      }

      console.log("[edit] Edit pipeline complete, reloading tracks...");
      reloadTracks()
        .then(() => console.log("[edit] Tracks reloaded successfully"))
        .catch((err) => console.error("[edit] Failed to reload tracks:", err))
        .finally(() => useEditorStore.getState().setIsEditing(false));
    } else if (editJob.status === "failed") {
      console.error("[edit] Edit pipeline failed:", editJob.error);
      useEditorStore.getState().setIsEditing(false);
      setErrorMessage("Something went wrong while processing your command. Please try again.");
    }
  }, [editJob, isEditing, setErrorMessage]);

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
      <div className="flex flex-1 overflow-hidden relative">
        {/* Sidebar */}
        <LayerPanel />

        {/* Timeline */}
        <TimelineArea onSeek={handleSeek} />

        {/* Edit progress toast */}
        {isEditing && <EditProgressToast />}
      </div>

      {/* Status bar */}
      <StatusBar />

      {/* Error modal — shared by both full pipeline and edit flow */}
      {errorMessage && (
        <EditErrorModal message={errorMessage} onClose={() => setErrorMessage(null)} />
      )}
    </div>
  );
}
