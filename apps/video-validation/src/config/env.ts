import dotenv from "dotenv";
import { z } from "zod";

dotenv.config({ path: ".env" });

const EnvSchema = z.object({
  VIDEO_VALIDATION_PORT: z.coerce.number().default(4300),
  DATABASE_URL: z.string().default("postgresql://postgres:postgres@localhost:5432/invision"),
  OPENAI_API_KEY: z.string().optional(),
  VIDEO_VALIDATION_TIMEOUT_MS: z.coerce.number().default(20000),
  VIDEO_VALIDATION_RETRY_COUNT: z.coerce.number().default(2),
  FFMPEG_BIN: z.string().default("ffmpeg"),
  FFPROBE_BIN: z.string().default("ffprobe"),
  TMP_DIR: z.string().default("/tmp/invision-video-validation")
});

export const env = EnvSchema.parse(process.env);
