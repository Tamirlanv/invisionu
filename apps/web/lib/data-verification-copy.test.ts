import { describe, expect, it } from "vitest";

import { buildDataVerificationCopy, FALLBACK_CENTER_BODY, FALLBACK_STAGE_HINT } from "./data-verification-copy";
import type { CandidateApplicationStatus } from "./candidate-status";

function buildStatus(overrides: Partial<CandidateApplicationStatus> = {}): CandidateApplicationStatus {
  return {
    current_stage: "initial_screening",
    submission_state: {
      state: "under_screening",
      submitted_at: "2026-01-01T00:00:00Z",
      locked: true,
      queue_status: "ready",
      queue_message: null,
    },
    stage_history: [],
    stage_descriptions: {},
    ...overrides,
  };
}

describe("buildDataVerificationCopy", () => {
  it("uses API note and stage description when present", () => {
    const out = buildDataVerificationCopy(
      buildStatus({
        stage_descriptions: {
          initial_screening: "Проверяем полноту и корректность данных.",
        },
        stage_history: [
          {
            to_stage: "initial_screening",
            entered_at: "2026-01-02T00:00:00Z",
            candidate_visible_note: "Ваша анкета принята на модерацию.",
          },
        ],
      }),
    );

    expect(out.stageHint).toBe("Проверяем полноту и корректность данных.");
    expect(out.centerBody).toBe("Ваша анкета принята на модерацию.");
  });

  it("falls back to default copy and degraded warning", () => {
    const out = buildDataVerificationCopy(
      buildStatus({
        submission_state: {
          state: "under_screening",
          submitted_at: "2026-01-01T00:00:00Z",
          locked: true,
          queue_status: "degraded",
          queue_message: null,
        },
      }),
    );

    expect(out.stageHint).toBe(FALLBACK_STAGE_HINT);
    expect(out.centerBody).toBe(FALLBACK_CENTER_BODY);
    expect(out.queueWarning).toContain("восстановления сервиса");
  });
});
