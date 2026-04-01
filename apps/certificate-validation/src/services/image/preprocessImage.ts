import { dirname, join } from "node:path";
import { mkdir } from "node:fs/promises";

import { runProcess } from "../../utils/process.js";

export async function preprocessImage(sourcePath: string): Promise<string> {
  const outDir = join(dirname(sourcePath), "processed");
  await mkdir(outDir, { recursive: true });
  const outPath = join(outDir, "preprocessed.png");
  await runProcess("ffmpeg", [
    "-y",
    "-i",
    sourcePath,
    "-vf",
    "eq=contrast=1.08:brightness=0.02,unsharp=5:5:1.0,transpose=2,transpose=2",
    outPath
  ]);
  return outPath;
}
