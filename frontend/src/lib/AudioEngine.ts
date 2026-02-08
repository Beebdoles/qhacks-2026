import type { TrackState } from "@/types/editor";

// Store getter — lazy to avoid circular imports
let getStoreState: (() => { tracks: TrackState[] }) | null = null;
export function setStoreGetter(fn: () => { tracks: TrackState[] }) {
  getStoreState = fn;
}

// Lazy-loaded Tone.js (avoid SSR)
let Tone: typeof import("tone") | null = null;
let Soundfont: typeof import("soundfont-player") | null = null;

async function loadDeps() {
  if (!Tone) Tone = await import("tone");
  if (!Soundfont) Soundfont = await import("soundfont-player");
}

interface TrackChannel {
  instrument: any; // soundfont-player instrument or drum kit wrapper
  gainNode: GainNode;
  dispose?: () => void;
}

class AudioEngine {
  private trackChannels: Map<number, TrackChannel> = new Map();
  private scheduledEvents: number[] = []; // Tone.Transport event IDs
  private started = false;
  private _onEnd: (() => void) | null = null;
  private endEventId: number | null = null;

  async ensureStarted(): Promise<void> {
    await loadDeps();
    if (!this.started && Tone) {
      await Tone.start();
      this.started = true;
    }
  }

  async loadTracks(tracks: TrackState[]): Promise<void> {
    await loadDeps();
    if (!Tone || !Soundfont) return;

    // Dispose old channels
    this.disposeChannels();

    const ctx = Tone.getContext().rawContext as AudioContext;

    for (const track of tracks) {
      const gainNode = ctx.createGain();
      gainNode.connect(ctx.destination);

      if (track.channel === 9) {
        // Synthesised drum kit with distinct sounds per GM note
        const { instrument, dispose } = this.createDrumKit(gainNode);
        this.trackChannels.set(track.index, { instrument, gainNode, dispose });
      } else {
        try {
          const instrument = await Soundfont.instrument(ctx, this.programToSoundfontName(track.programNumber), {
            gain: 1,
            destination: gainNode,
          });
          this.trackChannels.set(track.index, { instrument, gainNode });
        } catch (e) {
          console.warn(`Failed to load instrument for track ${track.index}:`, e);
          const instrument = await Soundfont.instrument(ctx, "acoustic_grand_piano" as any, {
            gain: 1,
            destination: gainNode,
          });
          this.trackChannels.set(track.index, { instrument, gainNode });
        }
      }
    }
  }

  private createDrumKit(gainNode: GainNode): { instrument: any; dispose: () => void } {
    if (!Tone) throw new Error("Tone not loaded");

    // --- KICK: deep sine thump ---
    const kick = new Tone.MembraneSynth({
      pitchDecay: 0.05,
      octaves: 8,
      oscillator: { type: "sine" },
      envelope: { attack: 0.001, decay: 0.4, sustain: 0, release: 0.4 },
    });
    kick.connect(gainNode);

    // --- SNARE: mid-range noise burst + body ---
    const snareBody = new Tone.MembraneSynth({
      pitchDecay: 0.01,
      octaves: 4,
      oscillator: { type: "triangle" },
      envelope: { attack: 0.001, decay: 0.1, sustain: 0, release: 0.1 },
    });
    snareBody.connect(gainNode);
    snareBody.volume.value = -8;

    const snareNoise = new Tone.NoiseSynth({
      noise: { type: "white" },
      envelope: { attack: 0.001, decay: 0.13, sustain: 0, release: 0.1 },
    });
    const snareBPF = new Tone.Filter(3000, "bandpass");
    snareNoise.connect(snareBPF);
    snareBPF.connect(gainNode);

    // --- HI-HAT: bright high-pass filtered noise ---
    const hihatNoise = new Tone.NoiseSynth({
      noise: { type: "white" },
      envelope: { attack: 0.001, decay: 0.04, sustain: 0, release: 0.02 },
    });
    const hihatHPF = new Tone.Filter(9000, "highpass");
    hihatNoise.connect(hihatHPF);
    hihatHPF.connect(gainNode);

    // --- OPEN HI-HAT: same but longer ---
    const openHatNoise = new Tone.NoiseSynth({
      noise: { type: "white" },
      envelope: { attack: 0.001, decay: 0.3, sustain: 0, release: 0.15 },
    });
    const openHatHPF = new Tone.Filter(8000, "highpass");
    openHatNoise.connect(openHatHPF);
    openHatHPF.connect(gainNode);

    // --- CYMBAL: long bright shimmer ---
    const cymbalNoise = new Tone.NoiseSynth({
      noise: { type: "white" },
      envelope: { attack: 0.001, decay: 0.8, sustain: 0, release: 0.5 },
    });
    const cymbalHPF = new Tone.Filter(6000, "highpass");
    cymbalNoise.connect(cymbalHPF);
    cymbalHPF.connect(gainNode);

    // --- TOM: pitched membrane ---
    const tom = new Tone.MembraneSynth({
      pitchDecay: 0.06,
      octaves: 4,
      oscillator: { type: "sine" },
      envelope: { attack: 0.001, decay: 0.25, sustain: 0, release: 0.2 },
    });
    tom.connect(gainNode);

    const instrument = {
      play(noteName: string, time: number, opts: { duration: number; gain: number }) {
        const midi = Tone!.Frequency(noteName).toMidi();
        const vel = Math.min(1, opts.gain ?? 0.8);

        if (midi === 35 || midi === 36) {
          // Bass drum — deep thump
          kick.triggerAttackRelease("C1", 0.5, time, vel);
        } else if (midi === 37) {
          // Side stick — short quiet body hit
          snareBody.triggerAttackRelease("E3", 0.05, time, vel * 0.6);
        } else if (midi === 38 || midi === 40) {
          // Snare — noise + body layered
          snareNoise.triggerAttackRelease(0.12, time);
          snareBody.triggerAttackRelease("C3", 0.08, time, vel);
        } else if (midi === 39) {
          // Hand clap — short noise burst
          snareNoise.triggerAttackRelease(0.06, time);
        } else if (midi === 42 || midi === 44) {
          // Closed hi-hat — very short bright noise
          hihatNoise.triggerAttackRelease(0.04, time);
        } else if (midi === 46) {
          // Open hi-hat — longer bright noise
          openHatNoise.triggerAttackRelease(0.25, time);
        } else if (midi === 49 || midi === 52 || midi === 55 || midi === 57) {
          // Crash cymbals — long shimmer
          cymbalNoise.triggerAttackRelease(0.7, time);
        } else if (midi === 51 || midi === 53 || midi === 59) {
          // Ride cymbal — medium bright
          openHatNoise.triggerAttackRelease(0.4, time);
        } else if (midi >= 41 && midi <= 50) {
          // Toms — pitched from low to high
          const freq = 60 + (midi - 41) * 20;
          tom.triggerAttackRelease(freq, 0.2, time, vel);
        } else {
          // Fallback: short hi-hat tick
          hihatNoise.triggerAttackRelease(0.03, time);
        }
      },
    };

    const dispose = () => {
      kick.dispose();
      snareBody.dispose();
      snareNoise.dispose();
      snareBPF.dispose();
      hihatNoise.dispose();
      hihatHPF.dispose();
      openHatNoise.dispose();
      openHatHPF.dispose();
      cymbalNoise.dispose();
      cymbalHPF.dispose();
      tom.dispose();
    };

    return { instrument, dispose };
  }

  private programToSoundfontName(program: number): string {
    // Convert GM program number to soundfont-player instrument name
    // soundfont-player uses snake_case names
    const names: Record<number, string> = {
      0: "acoustic_grand_piano", 1: "bright_acoustic_piano", 2: "electric_grand_piano",
      3: "honkytonk_piano", 4: "electric_piano_1", 5: "electric_piano_2",
      6: "harpsichord", 7: "clavinet", 8: "celesta", 9: "glockenspiel",
      10: "music_box", 11: "vibraphone", 12: "marimba", 13: "xylophone",
      14: "tubular_bells", 15: "dulcimer", 16: "drawbar_organ", 17: "percussive_organ",
      18: "rock_organ", 19: "church_organ", 20: "reed_organ", 21: "accordion",
      22: "harmonica", 23: "tango_accordion", 24: "acoustic_guitar_nylon",
      25: "acoustic_guitar_steel", 26: "electric_guitar_jazz", 27: "electric_guitar_clean",
      28: "electric_guitar_muted", 29: "overdriven_guitar", 30: "distortion_guitar",
      31: "guitar_harmonics", 32: "acoustic_bass", 33: "electric_bass_finger",
      34: "electric_bass_pick", 35: "fretless_bass", 36: "slap_bass_1", 37: "slap_bass_2",
      38: "synth_bass_1", 39: "synth_bass_2", 40: "violin", 41: "viola", 42: "cello",
      43: "contrabass", 44: "tremolo_strings", 45: "pizzicato_strings",
      46: "orchestral_harp", 47: "timpani", 48: "string_ensemble_1",
      49: "string_ensemble_2", 50: "synth_strings_1", 51: "synth_strings_2",
      52: "choir_aahs", 53: "voice_oohs", 54: "synth_choir", 55: "orchestra_hit",
      56: "trumpet", 57: "trombone", 58: "tuba", 59: "muted_trumpet",
      60: "french_horn", 61: "brass_section", 62: "synth_brass_1", 63: "synth_brass_2",
      64: "soprano_sax", 65: "alto_sax", 66: "tenor_sax", 67: "baritone_sax",
      68: "oboe", 69: "english_horn", 70: "bassoon", 71: "clarinet",
      72: "piccolo", 73: "flute", 74: "recorder", 75: "pan_flute",
      76: "blown_bottle", 77: "shakuhachi", 78: "whistle", 79: "ocarina",
      80: "lead_1_square", 81: "lead_2_sawtooth", 82: "lead_3_calliope",
      83: "lead_4_chiff", 84: "lead_5_charang", 85: "lead_6_voice",
      86: "lead_7_fifths", 87: "lead_8_bass__lead", 88: "pad_1_new_age",
      89: "pad_2_warm", 90: "pad_3_polysynth", 91: "pad_4_choir",
      92: "pad_5_bowed", 93: "pad_6_metallic", 94: "pad_7_halo", 95: "pad_8_sweep",
      96: "fx_1_rain", 97: "fx_2_soundtrack", 98: "fx_3_crystal", 99: "fx_4_atmosphere",
      100: "fx_5_brightness", 101: "fx_6_goblins", 102: "fx_7_echoes", 103: "fx_8_sci-fi",
      104: "sitar", 105: "banjo", 106: "shamisen", 107: "koto",
      108: "kalimba", 109: "bagpipe", 110: "fiddle", 111: "shanai",
      112: "tinkle_bell", 113: "agogo", 114: "steel_drums", 115: "woodblock",
      116: "taiko_drum", 117: "melodic_tom", 118: "synth_drum", 119: "reverse_cymbal",
      120: "guitar_fret_noise", 121: "breath_noise", 122: "seashore", 123: "bird_tweet",
      124: "telephone_ring", 125: "helicopter", 126: "applause", 127: "gunshot",
    };
    return names[program] ?? "acoustic_grand_piano";
  }

  schedulePlayback(tracks: TrackState[], startFrom = 0): void {
    if (!Tone) return;
    this.clearScheduled();

    const transport = Tone.getTransport();

    for (const track of tracks) {
      const channel = this.trackChannels.get(track.index);
      if (!channel) continue;

      for (const note of track.notes) {
        if (note.time + note.duration < startFrom) continue;

        const eventTime = Math.max(0, note.time - startFrom);
        const eventId = transport.schedule((time) => {
          // Check real-time mute state via store getter
          if (getStoreState) {
            const currentTrack = getStoreState().tracks.find((t: TrackState) => t.index === track.index);
            if (currentTrack?.muted || !currentTrack?.visible) return;
          }
          channel.instrument.play(note.name, time, {
            duration: note.duration,
            gain: note.velocity,
          });
        }, eventTime);
        this.scheduledEvents.push(eventId as unknown as number);
      }
    }

    // Schedule end event
    const maxEnd = tracks.reduce((max, t) => {
      const trackEnd = t.notes.reduce((m, n) => Math.max(m, n.time + n.duration), 0);
      return Math.max(max, trackEnd);
    }, 0);

    const endTime = Math.max(0, maxEnd - startFrom + 0.1);
    this.endEventId = transport.schedule(() => {
      this.stop();
      if (this._onEnd) this._onEnd();
    }, endTime) as unknown as number;
  }

  play(tracks: TrackState[], fromTime = 0): void {
    if (!Tone) return;
    const transport = Tone.getTransport();
    transport.cancel();
    transport.seconds = 0;
    this.schedulePlayback(tracks, fromTime);
    transport.start();
  }

  pause(): void {
    if (!Tone) return;
    Tone.getTransport().pause();
  }

  stop(): void {
    if (!Tone) return;
    const transport = Tone.getTransport();
    transport.stop();
    transport.cancel();
    transport.seconds = 0;
    this.clearScheduled();
  }

  seek(tracks: TrackState[], toTime: number): void {
    if (!Tone) return;
    const transport = Tone.getTransport();
    const wasPlaying = transport.state === "started";
    transport.stop();
    transport.cancel();
    this.clearScheduled();
    if (wasPlaying) {
      this.play(tracks, toTime);
    }
  }

  setTrackMute(trackIndex: number, muted: boolean): void {
    const channel = this.trackChannels.get(trackIndex);
    if (channel) {
      channel.gainNode.gain.value = muted ? 0 : 1;
    }
  }

  onEnd(cb: () => void): void {
    this._onEnd = cb;
  }

  getTransportSeconds(): number {
    if (!Tone) return 0;
    return Tone.getTransport().seconds;
  }

  getTransportState(): string {
    if (!Tone) return "stopped";
    return Tone.getTransport().state;
  }

  dispose(): void {
    this.stop();
    this.disposeChannels();
  }

  private clearScheduled(): void {
    if (!Tone) return;
    const transport = Tone.getTransport();
    for (const id of this.scheduledEvents) {
      transport.clear(id);
    }
    this.scheduledEvents = [];
    if (this.endEventId !== null) {
      transport.clear(this.endEventId);
      this.endEventId = null;
    }
  }

  private disposeChannels(): void {
    for (const [, channel] of this.trackChannels) {
      if (channel.dispose) channel.dispose();
      channel.gainNode.disconnect();
    }
    this.trackChannels.clear();
  }
}

// Singleton
export const audioEngine = new AudioEngine();
