import { describe, expect, it } from "vitest";
import {
  calculateCompletionPercent,
  getApplicationCompletionSummary,
  getSectionCompletionStatus,
  isSectionPayloadEmpty,
} from "./application-completion";

describe("application completion helpers", () => {
  it("detects empty payloads recursively", () => {
    expect(isSectionPayloadEmpty(undefined)).toBe(true);
    expect(isSectionPayloadEmpty({ a: "", b: false, c: [] })).toBe(true);
    expect(isSectionPayloadEmpty({ a: "", b: { c: "value" } })).toBe(false);
  });

  it("classifies section status as complete/incomplete/empty", () => {
    const sections = {
      personal: { is_complete: true, payload: { preferred_first_name: "Иван" } },
      contact: { is_complete: false, payload: { phone_e164: "+77000000000" } },
      education: { is_complete: false, payload: { presentation_video_url: "" } },
    };

    expect(getSectionCompletionStatus("personal", sections, new Set())).toBe("complete");
    expect(getSectionCompletionStatus("contact", sections, new Set())).toBe("incomplete");
    expect(getSectionCompletionStatus("education", sections, new Set())).toBe("empty");
    expect(getSectionCompletionStatus("internal_test", sections, new Set())).toBe("empty");
  });

  it("trusts missingSections over stale is_complete flags", () => {
    const sections = {
      personal: { is_complete: true, payload: { preferred_first_name: "Иван" } },
    };

    expect(getSectionCompletionStatus("personal", sections, new Set(["personal"]))).toBe("incomplete");
  });

  it("builds completion summary and dynamic percent from required sections", () => {
    const summary = getApplicationCompletionSummary({
      requiredSections: ["personal", "contact", "education"],
      missingSections: ["contact", "education"],
      sections: {
        personal: { is_complete: true, payload: { preferred_first_name: "Иван" } },
        contact: { is_complete: false, payload: { phone_e164: "+77000000000" } },
        education: { is_complete: false, payload: {} },
      },
      locked: false,
      emailVerified: true,
    });

    expect(summary.percent).toBe(33);
    expect(summary.completeCount).toBe(1);
    expect(summary.incompleteCount).toBe(1);
    expect(summary.emptyCount).toBe(1);
    expect(summary.canSubmit).toBe(false);
  });

  it("allows submit only when all required sections are complete", () => {
    const ready = getApplicationCompletionSummary({
      requiredSections: ["personal", "contact"],
      missingSections: [],
      sections: {
        personal: { is_complete: true, payload: { preferred_first_name: "Иван" } },
        contact: { is_complete: true, payload: { phone_e164: "+77000000000" } },
      },
      locked: false,
      emailVerified: true,
    });

    const locked = getApplicationCompletionSummary({
      requiredSections: ["personal", "contact"],
      missingSections: [],
      sections: {
        personal: { is_complete: true, payload: { preferred_first_name: "Иван" } },
        contact: { is_complete: true, payload: { phone_e164: "+77000000000" } },
      },
      locked: true,
      emailVerified: true,
    });

    expect(calculateCompletionPercent(2, 2)).toBe(100);
    expect(ready.canSubmit).toBe(true);
    expect(locked.canSubmit).toBe(false);
  });
});
