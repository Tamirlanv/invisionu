import dotenv from "dotenv";
import { z } from "zod";

dotenv.config({ path: ".env" });

const EnvSchema = z.object({
  CERT_VALIDATION_PORT: z.coerce.number().default(4400),
  DATABASE_URL: z.string().default("postgresql://postgres:postgres@localhost:5432/invision"),
  OPENAI_API_KEY: z.string().optional(),
  OCR_LANG: z.string().default("eng"),
  MAX_FILE_SIZE_BYTES: z.coerce.number().default(8 * 1024 * 1024),
  TOEFL_THRESHOLD: z.coerce.number().default(80)
});

export const env = EnvSchema.parse(process.env);
