import { mkdir } from "node:fs/promises";
import path from "node:path";

import { env } from "../../config/env.js";
import { runProcess } from "../../utils/process.js";

export async function extractAudioWav(videoPathOrUrl: string): Promise<string> {
  const outputDir = path.join(env.TMP_DIR, `audio-${Date.now()}`);
  await mkdir(outputDir, { recursive: true });
  const wavPath = path.join(outputDir, "audio.wav");
  await runProcess(env.FFMPEG_BIN, [
    "-y",
    "-i",
    videoPathOrUrl,
    "-vn",
    "-ac",
    "1",
    "-ar",
    "16000",
    "-acodec",
    "pcm_s16le",
    wavPath
  ]);
  return wavPath;
}
