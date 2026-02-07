import type { TrackState } from "@/types/editor";
import { NOTE_RANGE, LANE_HEIGHT } from "@/lib/constants";

interface NoteOptions {
  ctx: CanvasRenderingContext2D;
  width: number;
  height: number;
  scrollX: number;
  pixelsPerSecond: number;
  tracks: TrackState[];
}

export function drawNotes(opts: NoteOptions): void {
  const { ctx, width, height, scrollX, pixelsPerSecond, tracks } = opts;

  ctx.clearRect(0, 0, width, height);

  const startTime = scrollX / pixelsPerSecond;
  const endTime = (scrollX + width) / pixelsPerSecond;

  for (const track of tracks) {
    if (!track.visible) continue;

    const alpha = track.muted ? 0.4 : 1.0;

    for (const note of track.notes) {
      // Viewport culling — skip notes entirely outside visible range
      if (note.time + note.duration < startTime) continue;
      if (note.time > endTime) continue;
      if (note.midi < NOTE_RANGE.min || note.midi > NOTE_RANGE.max) continue;

      const x = note.time * pixelsPerSecond - scrollX;
      const w = Math.max(2, note.duration * pixelsPerSecond);
      const y = (NOTE_RANGE.max - note.midi) * LANE_HEIGHT;
      const h = LANE_HEIGHT;

      ctx.globalAlpha = alpha * note.velocity;
      ctx.fillStyle = track.color;
      ctx.fillRect(x, y, w, h);

      // Subtle border
      ctx.globalAlpha = alpha * 0.3;
      ctx.strokeStyle = "#000";
      ctx.lineWidth = 0.5;
      ctx.strokeRect(x, y, w, h);
    }
  }

  ctx.globalAlpha = 1.0;
}
