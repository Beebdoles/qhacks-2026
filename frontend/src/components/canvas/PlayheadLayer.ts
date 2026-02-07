interface PlayheadOptions {
  ctx: CanvasRenderingContext2D;
  width: number;
  height: number;
  scrollX: number;
  pixelsPerSecond: number;
  currentTime: number;
}

export function drawPlayhead(opts: PlayheadOptions): void {
  const { ctx, width, height, scrollX, pixelsPerSecond, currentTime } = opts;

  ctx.clearRect(0, 0, width, height);

  const x = currentTime * pixelsPerSecond - scrollX;

  // Only draw if visible
  if (x < 0 || x > width) return;

  // Playhead line
  ctx.strokeStyle = "#FFFFFF";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(x, 0);
  ctx.lineTo(x, height);
  ctx.stroke();

  // Small triangle at top
  ctx.fillStyle = "#FFFFFF";
  ctx.beginPath();
  ctx.moveTo(x - 5, 0);
  ctx.lineTo(x + 5, 0);
  ctx.lineTo(x, 8);
  ctx.closePath();
  ctx.fill();
}
