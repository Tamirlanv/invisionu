/** Server-side fetch to FastAPI (Docker: http://api:8000). Browser uses same-origin `/api/v1` via rewrites. */
export function apiServerBase(): string {
  return process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}
