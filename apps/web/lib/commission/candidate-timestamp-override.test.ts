import { describe, expect, it } from "vitest";
import {
  formatDateDDMMYY,
  formatDateTimeDDMMYYHHMM,
  formatTimeHHMM,
  isTargetCandidateName,
  resolveDisplayDate,
} from "./candidate-timestamp-override";

describe("candidate timestamp override", () => {
  it("matches target candidate by normalized full name", () => {
    expect(isTargetCandidateName("Кузнецов Илья")).toBe(true);
    expect(isTargetCandidateName("  иЛья   КУЗНЕЦОВ ")).toBe(true);
    expect(isTargetCandidateName("Кузнецов Илья Петрович")).toBe(true);
    expect(isTargetCandidateName("Илья Андреевич Кузнецов")).toBe(true);
    expect(isTargetCandidateName("Кузнецова Илья")).toBe(false);
    expect(isTargetCandidateName("Кузнецов Игорь")).toBe(false);
  });

  it("returns fixed display date for target candidate", () => {
    const d = resolveDisplayDate("2025-01-01T10:11:12.000Z", "Кузнецов Илья");
    expect(d).not.toBeNull();
    expect(formatDateDDMMYY(d!)).toBe("05.04.26");
    expect(formatTimeHHMM(d!)).toBe("20:58");
    expect(formatDateTimeDDMMYYHHMM(d!)).toBe("05.04.26 20:58");
  });

  it("returns parsed raw date for non-target candidate", () => {
    const d = resolveDisplayDate("2026-01-02T03:04:00.000Z", "Иванов Иван");
    expect(d).not.toBeNull();
    expect(d!.toISOString()).toBe("2026-01-02T03:04:00.000Z");
  });

  it("returns null for non-target with invalid raw date", () => {
    expect(resolveDisplayDate("bad-value", "Иванов Иван")).toBeNull();
  });
});
