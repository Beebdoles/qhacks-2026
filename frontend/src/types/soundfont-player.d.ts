declare module "soundfont-player" {
  interface InstrumentOptions {
    gain?: number;
    destination?: AudioNode;
    soundfont?: string;
  }

  interface Player {
    play(note: string, when?: number, options?: { duration?: number; gain?: number }): AudioNode;
    stop(): void;
  }

  export function instrument(
    ac: AudioContext,
    name: string,
    options?: InstrumentOptions
  ): Promise<Player>;
}
