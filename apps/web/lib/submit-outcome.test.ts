import { describe, expect, it } from "vitest";

import { getSubmitSuccessMessage } from "./submit-outcome";

describe("submit outcome messaging", () => {
  it("shows normal success for ready queue", () => {
    expect(getSubmitSuccessMessage({ queue_status: "ready" })).toBe("Анкета успешно отправлена.");
  });

  it("shows degraded success for queue failures", () => {
    expect(
      getSubmitSuccessMessage({
        queue_status: "degraded",
        queue_message: "Анкета отправлена, обработка ожидает очередь.",
      }),
    ).toBe("Анкета отправлена, обработка ожидает очередь.");
  });
});
