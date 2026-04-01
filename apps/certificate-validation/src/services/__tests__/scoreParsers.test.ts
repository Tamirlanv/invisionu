import { describe, expect, it } from "vitest";

import { parseEntScore, parseIeltsOverall, parseToeflScore } from "../extraction/scoreParsers.js";

describe("score parsers", () => {
  it("parses ielts decimal", () => {
    expect(parseIeltsOverall("Overall Band Score: 6.5")).toBe(6.5);
  });

  it("parses toefl", () => {
    expect(parseToeflScore("TOEFL Total Score 101")).toBe(101);
  });

  it("parses ent", () => {
    expect(parseEntScore("ЕНТ итоговый балл: 114")).toBe(114);
  });
});
