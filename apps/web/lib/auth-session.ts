export type AuthScope = "candidate" | "commission";

type AuthTokens = {
  accessToken: string;
  refreshToken: string;
};

const ACCESS_KEY: Record<AuthScope, string> = {
  candidate: "invision_auth_candidate_access",
  commission: "invision_auth_commission_access",
};

const REFRESH_KEY: Record<AuthScope, string> = {
  candidate: "invision_auth_candidate_refresh",
  commission: "invision_auth_commission_refresh",
};

function hasStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function getAuthScopeFromPathname(pathname: string | null | undefined): AuthScope {
  if ((pathname ?? "").startsWith("/commission")) return "commission";
  return "candidate";
}

export function getAuthScopeFromApiPath(relPath: string): AuthScope {
  if (relPath.startsWith("/api/v1/commission")) return "commission";
  return "candidate";
}

export function storeAuthTokens(scope: AuthScope, tokens: AuthTokens): void {
  if (!hasStorage()) return;
  window.localStorage.setItem(ACCESS_KEY[scope], tokens.accessToken);
  window.localStorage.setItem(REFRESH_KEY[scope], tokens.refreshToken);
}

export function getAccessToken(scope: AuthScope): string | null {
  if (!hasStorage()) return null;
  return window.localStorage.getItem(ACCESS_KEY[scope]);
}

export function getRefreshToken(scope: AuthScope): string | null {
  if (!hasStorage()) return null;
  return window.localStorage.getItem(REFRESH_KEY[scope]);
}

export function clearAuthTokens(scope: AuthScope): void {
  if (!hasStorage()) return;
  window.localStorage.removeItem(ACCESS_KEY[scope]);
  window.localStorage.removeItem(REFRESH_KEY[scope]);
}
