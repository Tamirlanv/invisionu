import { describe, expect, it } from "vitest";
import { permissionsFromRole } from "./permissions";

describe("permissionsFromRole", () => {
  it("treats null commission role as read-only viewer-like", () => {
    const p = permissionsFromRole(null);
    expect(p.canOpenCandidate).toBe(true);
    expect(p.canComment).toBe(false);
    expect(p.canSetStageStatus).toBe(false);
  });

  it("allows reviewer to mutate review fields", () => {
    const p = permissionsFromRole("reviewer");
    expect(p.canSetRubric).toBe(true);
    expect(p.canSetStageStatus).toBe(true);
    expect(p.canComment).toBe(true);
    expect(p.canMove).toBe(true);
  });

  it("keeps viewer in read-only mode", () => {
    const p = permissionsFromRole("viewer");
    expect(p.canComment).toBe(false);
    expect(p.canMove).toBe(false);
  });
});
