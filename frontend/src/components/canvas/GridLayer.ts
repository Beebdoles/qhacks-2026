import { NOTE_RANGE, LANE_HEIGHT } from "@/lib/constants";

interface GridOptions {
  ctx: CanvasRenderingContext2D;
  width: number;
  height: number;
  scrollX: number;
  pixelsPerSecond: number;
  bpm: number;
  timeSignature: [number, number];
}

export function drawGrid(opts: GridOptions): void {
  const { ctx, width, height, scrollX, pixelsPerSecond, bpm, timeSignature } = opts;

  ctx.clearRect(0, 0, width, height);

  const secondsPerBeat = 60 / bpm;
  const beatsPerBar = timeSignature[0];
  const secondsPerBar = secondsPerBeat * beatsPerBar;
  const pixelsPerBeat = secondsPerBeat * pixelsPerSecond;
  const pixelsPerBar = secondsPerBar * pixelsPerSecond;

  // Visible time range
  const startTime = scrollX / pixelsPerSecond;
  const endTime = (scrollX + width) / pixelsPerSecond;

  // Draw horizontal lane lines (every octave or every few notes for readability)
  const totalNotes = NOTE_RANGE.max - NOTE_RANGE.min + 1;
  for (let i = 0; i <= totalNotes; i++) {
    const noteNum = NOTE_RANGE.min + i;
    const y = (NOTE_RANGE.max - noteNum) * LANE_HEIGHT;

    // Draw C note lines more prominently
    if (noteNum % 12 === 0) {
      ctx.strokeStyle = "#3A3A3A";
      ctx.lineWidth = 1;
    } else {
      ctx.strokeStyle = "#1E1E1E";
      ctx.lineWidth = 0.5;
    }

    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }

  // Draw vertical beat/bar lines
  const firstBar = Math.floor(startTime / secondsPerBar);
  const lastBar = Math.ceil(endTime / secondsPerBar);

  for (let bar = firstBar; bar <= lastBar; bar++) {
    const barTime = bar * secondsPerBar;
    const barX = barTime * pixelsPerSecond - scrollX;

    // Bar line
    ctx.strokeStyle = "#3A3A3A";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(barX, 0);
    ctx.lineTo(barX, height);
    ctx.stroke();

    // Beat lines within bar
    for (let beat = 1; beat < beatsPerBar; beat++) {
      const beatTime = barTime + beat * secondsPerBeat;
      const beatX = beatTime * pixelsPerSecond - scrollX;

      ctx.strokeStyle = "#1E1E1E";
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.moveTo(beatX, 0);
      ctx.lineTo(beatX, height);
      ctx.stroke();
    }
  }
}
