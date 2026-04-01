import Fastify from "fastify";

import { registerValidationOrchestratorRoutes } from "./api/routes/validationOrchestrator.js";
import { env } from "./config/env.js";
import { startCertificateWorker } from "./queue/workers/certificateWorker.js";
import { startLinkWorker } from "./queue/workers/linkWorker.js";
import { startVideoWorker } from "./queue/workers/videoWorker.js";

async function start(): Promise<void> {
  const app = Fastify({ logger: true });
  await registerValidationOrchestratorRoutes(app);
  startLinkWorker();
  startVideoWorker();
  startCertificateWorker();
  await app.listen({ port: env.ORCHESTRATOR_PORT, host: "0.0.0.0" });
}

start().catch((error) => {
  // eslint-disable-next-line no-console
  console.error(error);
  process.exit(1);
});
