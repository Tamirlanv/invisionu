import { env } from "../../config/env.js";
import { runProcess } from "../../utils/process.js";
import { VideoMetadata } from "../types.js";

type FfprobeStream = {
  codec_type?: string;
  codec_name?: string;
  width?: number;
  height?: number;
  duration?: string;
};

type FfprobeJson = {
  streams?: FfprobeStream[];
  format?: { duration?: string };
};

export async function extractMetadata(videoPathOrUrl: string): Promise<VideoMetadata> {
  const args = [
    "-v",
    "error",
    "-show_streams",
    "-show_format",
    "-of",
    "json",
    videoPathOrUrl
  ];
  const { stdout } = await runProcess(env.FFPROBE_BIN, args);
  const parsed = JSON.parse(stdout) as FfprobeJson;
  const streams = parsed.streams ?? [];
  const videoStream = streams.find((s) => s.codec_type === "video");
  const audioStream = streams.find((s) => s.codec_type === "audio");
  const rawDuration = parsed.format?.duration ?? videoStream?.duration ?? null;

  return {
    durationSec: rawDuration ? Number(rawDuration) : null,
    width: videoStream?.width ?? null,
    height: videoStream?.height ?? null,
    hasVideoTrack: Boolean(videoStream),
    hasAudioTrack: Boolean(audioStream),
    codecVideo: videoStream?.codec_name ?? null,
    codecAudio: audioStream?.codec_name ?? null
  };
}
