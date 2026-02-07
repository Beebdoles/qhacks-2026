"use client";

import { useEffect, useState } from "react";

const CDN_URL =
  "https://cdn.jsdelivr.net/combine/npm/tone@14.7.77,npm/@magenta/music@1.23.1/es6/core.js,npm/html-midi-player@1.5.0";

interface Props {
  midiUrl: string;
}

export default function MidiPlayer({ midiUrl }: Props) {
  const [status, setStatus] = useState<"loading" | "ready" | "error">(
    "loading"
  );

  useEffect(() => {
    if (customElements.get("midi-player")) {
      setStatus("ready");
      return;
    }

    const script = document.createElement("script");
    script.src = CDN_URL;
    script.async = true;

    script.onload = () => setStatus("ready");
    script.onerror = () => setStatus("error");

    document.head.appendChild(script);

    return () => {
      // Don't remove — the custom elements are registered globally
    };
  }, []);

  if (status === "loading") {
    return (
      <div className="w-full flex items-center justify-center py-8 text-sm text-zinc-500">
        <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mr-2" />
        Loading MIDI player...
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="w-full bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-xl p-4 text-sm text-red-600 dark:text-red-400">
        Failed to load MIDI player. Check your network connection and reload.
      </div>
    );
  }

  return (
    <div className="w-full space-y-2">
      <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
        MIDI Playback
      </h3>
      <midi-visualizer
        id="midi-visualizer"
        type="piano-roll"
        src={midiUrl}
      />
      <midi-player
        src={midiUrl}
        sound-font
        visualizer="#midi-visualizer"
      />
    </div>
  );
}
