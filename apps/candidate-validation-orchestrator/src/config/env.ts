import dotenv from "dotenv";
import { z } from "zod";

dotenv.config({ path: ".env" });

const EnvSchema = z.object({
  ORCHESTRATOR_PORT: z.coerce.number().default(4500),
  DATABASE_URL: z.string().default("postgresql://postgres:postgres@localhost:5432/invision"),
  REDIS_URL: z.string().default("redis://localhost:6379/0"),
  LINK_VALIDATION_URL: z.string().default("http://localhost:8000/api/v1/links/validate"),
  VIDEO_VALIDATION_URL: z.string().default("http://localhost:4300/video-validation/validate"),
  CERTIFICATE_VALIDATION_URL: z.string().default("http://localhost:4400/certificate-validation/validate")
});

export const env = EnvSchema.parse(process.env);
