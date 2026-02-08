"use client";

import { useEffect, useRef } from "react";
import { useEditorStore } from "@/stores/editorStore";
import { audioEngine } from "@/lib/AudioEngine";

export function useAnimationFrame() {
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    let active = true;

    const tick = () => {
      if (!active) return;
      const { transport, setCurrentTime } = useEditorStore.getState();
      if (transport.playing) {
        const seconds = audioEngine.getTransportSeconds();
        setCurrentTime(seconds);
      }
      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);

    return () => {
      active = false;
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, []);
}
