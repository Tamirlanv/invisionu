import { describe, expect, it } from "vitest";
import { getAuthScopeFromApiPath, getAuthScopeFromPathname } from "./auth-session";

describe("auth-session scope helpers", () => {
  it("resolves commission scope from pathname", () => {
    expect(getAuthScopeFromPathname("/commission")).toBe("commission");
    expect(getAuthScopeFromPathname("/commission/applications/123")).toBe("commission");
  });

  it("resolves candidate scope from non-commission pathname", () => {
    expect(getAuthScopeFromPathname("/application/personal")).toBe("candidate");
    expect(getAuthScopeFromPathname("")).toBe("candidate");
    expect(getAuthScopeFromPathname(undefined)).toBe("candidate");
  });

  it("resolves commission scope from commission API prefix", () => {
    expect(getAuthScopeFromApiPath("/api/v1/commission/me")).toBe("commission");
    expect(getAuthScopeFromApiPath("/api/v1/commission/applications/123/personal-info")).toBe("commission");
  });

  it("defaults to candidate scope for other API routes", () => {
    expect(getAuthScopeFromApiPath("/api/v1/candidates/me")).toBe("candidate");
    expect(getAuthScopeFromApiPath("/api/v1/auth/refresh")).toBe("candidate");
  });
});
