import { CheckType } from "../services/types.js";
import { getCertificateQueue, getLinkQueue, getVideoQueue } from "./queues.js";

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("Queue enqueue timeout")), ms);
    promise
      .then((v) => {
        clearTimeout(timer);
        resolve(v);
      })
      .catch((e) => {
        clearTimeout(timer);
        reject(e);
      });
  });
}

export async function enqueueCheck(
  checkType: CheckType,
  payload: Record<string, unknown>
): Promise<void> {
  const jobOptions = { attempts: 3, backoff: { type: "exponential" as const, delay: 500 } };
  if (checkType === "links") await withTimeout(getLinkQueue().add("check", payload, jobOptions), 2000);
  if (checkType === "videoPresentation") await withTimeout(getVideoQueue().add("check", payload, jobOptions), 2000);
  if (checkType === "certificates") await withTimeout(getCertificateQueue().add("check", payload, jobOptions), 2000);
}
