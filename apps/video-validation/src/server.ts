import Fastify from "fastify";

import { registerVideoValidationRoutes } from "./api/routes/videoValidation.js";
import { env } from "./config/env.js";

async function start(): Promise<void> {
  const app = Fastify({ logger: true });
  await registerVideoValidationRoutes(app);
  await app.listen({ port: env.VIDEO_VALIDATION_PORT, host: "0.0.0.0" });
}

start().catch((error) => {
  // eslint-disable-next-line no-console
  console.error(error);
  process.exit(1);
});
