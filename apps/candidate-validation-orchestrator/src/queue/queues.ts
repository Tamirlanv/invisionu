import { Queue } from "bullmq";

import { env } from "../config/env.js";

const redisUrl = new URL(env.REDIS_URL);
const connection = {
  host: redisUrl.hostname,
  port: Number(redisUrl.port || 6379),
  db: Number((redisUrl.pathname || "/0").replace("/", "")),
  password: redisUrl.password || undefined
};

export function getLinkQueue(): Queue {
  return new Queue("invision_orchestrator_link", { connection });
}

export function getVideoQueue(): Queue {
  return new Queue("invision_orchestrator_video", { connection });
}

export function getCertificateQueue(): Queue {
  return new Queue("invision_orchestrator_certificate", { connection });
}

export function queueConnection() {
  return connection;
}
