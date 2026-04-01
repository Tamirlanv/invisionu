import { performance } from "node:perf_hooks";
import { env } from "../../config/env.js";
import { MediaProbeResult } from "../types.js";

const RETRYABLE_STATUSES = new Set([408, 429, 500, 502, 503, 504]);

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function probeMediaUrl(url: string): Promise<MediaProbeResult> {
  let lastError: string | null = null;

  for (let i = 0; i < env.VIDEO_VALIDATION_RETRY_COUNT; i += 1) {
    const startedAt = performance.now();
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), env.VIDEO_VALIDATION_TIMEOUT_MS);
      let response = await fetch(url, { method: "HEAD", redirect: "follow", signal: controller.signal });
      if ([405, 403, 400].includes(response.status)) {
        response = await fetch(url, {
          method: "GET",
          redirect: "follow",
          signal: controller.signal,
          headers: { Range: "bytes=0-4096" }
        });
      }
      clearTimeout(timeout);

      const elapsed = Math.round(performance.now() - startedAt);
      const redirected = response.url !== url;
      const statusCode = response.status;
      if (RETRYABLE_STATUSES.has(statusCode) && i < env.VIDEO_VALIDATION_RETRY_COUNT - 1) {
        await sleep(250 * (i + 1));
        continue;
      }

      return {
        finalUrl: response.url ?? null,
        statusCode,
        contentType: response.headers.get("content-type"),
        contentLength: response.headers.get("content-length")
          ? Number(response.headers.get("content-length"))
          : null,
        redirected,
        redirectCount: redirected ? 1 : 0,
        responseTimeMs: elapsed,
        error: null
      };
    } catch (error) {
      lastError = error instanceof Error ? error.message : "Unknown media probe error";
      if (i < env.VIDEO_VALIDATION_RETRY_COUNT - 1) {
        await sleep(200 * (i + 1));
      }
    }
  }

  return {
    finalUrl: null,
    statusCode: null,
    contentType: null,
    contentLength: null,
    redirected: false,
    redirectCount: 0,
    responseTimeMs: null,
    error: lastError
  };
}
