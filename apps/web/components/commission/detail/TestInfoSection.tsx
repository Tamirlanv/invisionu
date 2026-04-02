"use client";

import type { CommissionApplicationTestInfoView } from "@/lib/commission/types";

type Props = {
  data: CommissionApplicationTestInfoView;
  onNext?: () => void;
};

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

export function TestInfoSection({ data, onNext }: Props) {
  const profile = data.personalityProfile;

  const oddQuestions = data.questions.filter((_, i) => i % 2 === 0);
  const evenQuestions = data.questions.filter((_, i) => i % 2 === 1);

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
