import { URL } from "node:url";
import { UrlValidationResult } from "../types.js";

const ALLOWED_SCHEMES = new Set(["http:", "https:"]);
const DENIED_SCHEMES = new Set(["javascript:", "data:", "file:"]);

export function validateVideoUrl(rawUrl: string): UrlValidationResult {
  const input = rawUrl.trim();
  if (!input) {
    return { isValid: false, normalizedUrl: null, errors: ["URL is empty"] };
  }

  let maybeUrl = input;
  if (!maybeUrl.includes("://")) {
    maybeUrl = `https://${maybeUrl}`;
  }

  try {
    const parsed = new URL(maybeUrl);
    if (DENIED_SCHEMES.has(parsed.protocol)) {
      return { isValid: false, normalizedUrl: null, errors: ["Denied URL scheme"] };
    }
    if (!ALLOWED_SCHEMES.has(parsed.protocol)) {
      return { isValid: false, normalizedUrl: null, errors: ["Unsupported URL scheme"] };
    }
    if (!parsed.hostname) {
      return { isValid: false, normalizedUrl: null, errors: ["Hostname is missing"] };
    }
    parsed.hash = "";
    return { isValid: true, normalizedUrl: parsed.toString(), errors: [] };
  } catch {
    return { isValid: false, normalizedUrl: null, errors: ["Malformed URL"] };
  }
}
