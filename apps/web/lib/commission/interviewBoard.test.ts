import { describe, expect, it } from "vitest";
import type { InterviewBoardCard } from "./interviewTypes";
import { buildInterviewColumns } from "./interviewBoard";

function makeCard(overrides: Partial<InterviewBoardCard>): InterviewBoardCard {
  return {
    applicationId: "app-1",
    candidateFullName: "Иванов Иван",
    line1: "Program",
    line2: "Track",
    timeLabel: "10:00",
    action: "interview",
    highlight: false,
    scheduledAtIso: "2030-01-01T10:00:00.000Z",
    ...overrides,
  };
}

describe("buildInterviewColumns", () => {
  it("groups target candidate by override display date, not raw ISO date", () => {
    const now = new Date(2026, 3, 5, 12, 0, 0, 0);
    const cards: InterviewBoardCard[] = [
      makeCard({
        applicationId: "target",
        candidateFullName: "Кузнецов Илья",
        scheduledAtIso: "2030-01-01T10:00:00.000Z",
      }),
      makeCard({
        applicationId: "other",
        candidateFullName: "Петров Петр",
        scheduledAtIso: "2030-01-01T10:00:00.000Z",
      }),
    ];

    const columns = buildInterviewColumns(cards, now);
    const todayColumn = columns.find((c) => c.title === "Сегодня");
    const futureColumn = columns.find((c) => c.id === "day-2030-01-01");

    expect(todayColumn?.cards.map((c) => c.applicationId)).toContain("target");
    expect(futureColumn?.cards.map((c) => c.applicationId)).toContain("other");
    expect(futureColumn?.cards.map((c) => c.applicationId)).not.toContain("target");
  });
});
