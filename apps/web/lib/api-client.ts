import { apiServerBase } from "./config";

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function parseJsonSafe(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function apiBaseUrl(): string {
  if (typeof window === "undefined") {
    return apiServerBase();
  }
  return "";
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit & { json?: unknown } = {},
): Promise<T> {
  const { json, headers, ...rest } = init;
  const base = apiBaseUrl();
  const rel = path.startsWith("/api/v1") ? path : `/api/v1${path.startsWith("/") ? path : `/${path}`}`;
  const url = path.startsWith("http") ? path : `${base}${rel}`;
  const h = new Headers(headers);
  if (json !== undefined) {
    h.set("Content-Type", "application/json");
  }
  const res = await fetch(url, {
    ...rest,
    headers: h,
    body: json !== undefined ? JSON.stringify(json) : rest.body,
    credentials: "include",
    cache: "no-store",
  });
  const data = await parseJsonSafe(res);
  if (!res.ok) {
    const msg =
      typeof data === "object" && data && "detail" in data
        ? JSON.stringify((data as { detail: unknown }).detail)
        : `Request failed (${res.status})`;
    throw new ApiError(msg, res.status, data);
  }
  return data as T;
}

export async function refreshSession(): Promise<boolean> {
  try {
    await apiFetch("/api/v1/auth/refresh", { method: "POST" });
    return true;
  } catch {
    return false;
  }
}
