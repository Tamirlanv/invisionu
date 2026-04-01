import { mkdir, readdir } from "node:fs/promises";
import path from "node:path";

import { env } from "../../config/env.js";
import { runProcess } from "../../utils/process.js";

export async function sampleFrames(videoPathOrUrl: string, durationSec: number | null): Promise<{
  framePaths: string[];
  sampledTimestampsSec: number[];
}> {
  const total = durationSec && durationSec > 0 ? durationSec : 30;
  const frameCount = Math.max(5, Math.min(10, Math.floor(total / 10) || 5));
  const sampledTimestampsSec = Array.from({ length: frameCount }, (_, i) =>
    Number((((i + 1) * total) / (frameCount + 1)).toFixed(2))
  );

  const outputDir = path.join(env.TMP_DIR, `frames-${Date.now()}`);
  await mkdir(outputDir, { recursive: true });

  const fps = frameCount / total;
  const outputPattern = path.join(outputDir, "frame-%03d.jpg");
  await runProcess(env.FFMPEG_BIN, [
    "-y",
    "-i",
    videoPathOrUrl,
    "-vf",
    `fps=${fps}`,
    "-q:v",
    "2",
    outputPattern
  ]);

  const files = (await readdir(outputDir))
    .filter((f) => f.endsWith(".jpg"))
    .sort()
    .map((f) => path.join(outputDir, f));
  return { framePaths: files, sampledTimestampsSec };
}
