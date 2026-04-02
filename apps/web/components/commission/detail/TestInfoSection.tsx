"use client";

import type { CommissionApplicationTestInfoView } from "@/lib/commission/types";

type Props = {
  data: CommissionApplicationTestInfoView;
  onNext?: () => void;
};

const TRAIT_LABELS: Record<string, string> = {
  INI: "Мотивированность",
  RES: "Лидерские качества",
  COL: "Уверенность",
  ADP: "Стрессоустойчивость",
  REF: "Рефлексивность",
};

const SCORE_ROW_1_KEYS = ["INI", "RES"] as const;
const SCORE_ROW_2_KEYS = ["COL", "ADP"] as const;
const MAX_PER_TRAIT = 5;

function scaleToFive(raw: number, maxRaw: number): number {
  if (maxRaw <= 0) return 0;
  return Math.round((raw / maxRaw) * MAX_PER_TRAIT);
}

const sectionTitle: React.CSSProperties = {
  margin: 0,
  fontSize: 20,
  fontWeight: 550,
  color: "#262626",
  letterSpacing: "-0.6px",
  lineHeight: "20px",
};

const labelStyle: React.CSSProperties = {
  margin: 0,
  fontSize: 14,
  fontWeight: 350,
  color: "#626262",
  letterSpacing: "-0.42px",
  lineHeight: "14px",
};

const valueStyle: React.CSSProperties = {
  margin: 0,
  fontSize: 14,
  fontWeight: 350,
  color: "#262626",
  letterSpacing: "-0.42px",
  lineHeight: "14px",
};

function ScoreCard({
  label,
  value,
  max,
  highlight,
}: {
  label: string;
  value: number;
  max: number;
  highlight?: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: 24,
        alignItems: "center",
        padding: 24,
        borderRadius: 16,
        border: highlight ? "2px solid #98da00" : "1px solid #f1f1f1",
        background: "#fff",
      }}
    >
      <p style={{ ...sectionTitle, whiteSpace: "nowrap" }}>{label}</p>
      <p
        style={{
          margin: 0,
          fontSize: 36,
          fontWeight: 550,
          color: "#98da00",
          letterSpacing: "-1.08px",
          lineHeight: "36px",
          whiteSpace: "nowrap",
        }}
      >
        {value}/{max}
      </p>
    </div>
  );
}

export function TestInfoSection({ data, onNext }: Props) {
  const profile = data.personalityProfile;
  const rawScores = profile?.rawScores ?? {};

  const maxTraitRaw = Math.max(...Object.values(rawScores), 1);

  const oddQuestions = data.questions.filter((_, i) => i % 2 === 0);
  const evenQuestions = data.questions.filter((_, i) => i % 2 === 1);

  const totalScore = Object.values(rawScores).reduce((a, b) => a + b, 0);
  const totalMax = Object.keys(rawScores).length * MAX_PER_TRAIT;

  return (
    <div style={{ display: "grid", gap: 24, minWidth: 0 }}>
      {/* Header */}
      <h2 style={sectionTitle}>Тест на тип личности</h2>

      {/* Personality / Language fields */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div style={{ display: "grid", gap: 8 }}>
          <p style={labelStyle}>Личность</p>
          <p style={valueStyle}>{profile?.profileTitle ?? "—"}</p>
        </div>
        <div style={{ display: "grid", gap: 8 }}>
          <p style={labelStyle}>Язык теста</p>
          <p style={valueStyle}>{data.testLang}</p>
        </div>
      </div>

      {/* Test results heading */}
      <h2 style={sectionTitle}>Результаты теста</h2>

      {/* Two-column Q&A grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 40px" }}>
        {/* Left column: odd-indexed questions (1, 3, 5, ...) */}
        <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
          {oddQuestions.map((q) => (
            <div key={q.questionId} style={{ display: "grid", gap: 4 }}>
              <p style={labelStyle}>
                {q.index}. {q.prompt}
              </p>
              <p style={valueStyle}>{q.selectedAnswer ?? "—"}</p>
            </div>
          ))}
        </div>
        {/* Right column: even-indexed questions (2, 4, 6, ...) */}
        <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
          {evenQuestions.map((q) => (
            <div key={q.questionId} style={{ display: "grid", gap: 4 }}>
              <p style={labelStyle}>
                {q.index}. {q.prompt}
              </p>
              <p style={valueStyle}>{q.selectedAnswer ?? "—"}</p>
            </div>
          ))}
        </div>
      </div>

      {/* AI summary heading */}
      <h2 style={sectionTitle}>ИИ сводка</h2>

      {/* Score cards row 1 */}
      <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
        {SCORE_ROW_1_KEYS.map((key) => (
          <ScoreCard
            key={key}
            label={TRAIT_LABELS[key] ?? key}
            value={scaleToFive(rawScores[key] ?? 0, maxTraitRaw)}
            max={MAX_PER_TRAIT}
          />
        ))}
      </div>

      {/* Score cards row 2 + total */}
      <div style={{ display: "flex", gap: 32, flexWrap: "wrap" }}>
        {SCORE_ROW_2_KEYS.map((key) => (
          <ScoreCard
            key={key}
            label={TRAIT_LABELS[key] ?? key}
            value={scaleToFive(rawScores[key] ?? 0, maxTraitRaw)}
            max={MAX_PER_TRAIT}
          />
        ))}
        <ScoreCard
          label="Итог"
          value={SCORE_ROW_1_KEYS.concat(SCORE_ROW_2_KEYS).reduce(
            (sum, k) => sum + scaleToFive(rawScores[k] ?? 0, maxTraitRaw),
            0,
          )}
          max={totalMax > 0 ? SCORE_ROW_1_KEYS.length * MAX_PER_TRAIT + SCORE_ROW_2_KEYS.length * MAX_PER_TRAIT : 20}
          highlight
        />
      </div>

      {/* Далее button */}
      {onNext ? (
        <div style={{ display: "flex", justifyContent: "center", marginTop: 16 }}>
          <button
            type="button"
            onClick={onNext}
            style={{
              padding: "12px 24px",
              borderRadius: 8,
              border: "none",
              background: "#98da00",
              color: "#fff",
              fontSize: 14,
              fontWeight: 350,
              letterSpacing: "-0.42px",
              cursor: "pointer",
            }}
          >
            Далее
          </button>
        </div>
      ) : null}
    </div>
  );
}
