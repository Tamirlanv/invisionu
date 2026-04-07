"use client";

import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { ApiError } from "@/lib/api-client";
import { resolveDisplayDate } from "@/lib/commission/candidate-timestamp-override";
import { getCommissionAiInterviewCandidateSession } from "@/lib/commission/query";
import type { CommissionAiInterviewSessionView } from "@/lib/commission/types";
function resolutionConfidenceLabel(
  c: NonNullable<CommissionAiInterviewSessionView["resolutionSummary"]>["confidence"],
): string {
  if (c === "high") return "высокая";
  if (c === "medium") return "средняя";
  return "низкая";
}

type Props = {
  applicationId: string;
  isActive: boolean;
  candidateFullName?: string | null;
};

function formatDateTimeForPanel(raw: string, candidateFullName: string | null | undefined): string {
  const dt = resolveDisplayDate(raw, candidateFullName);
  if (!dt) return raw;
  return dt.toLocaleString("ru-RU");
}

export function CommissionCandidateAiInterviewPanel({ applicationId, isActive, candidateFullName }: Props) {
  const [data, setData] = useState<CommissionAiInterviewSessionView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await getCommissionAiInterviewCandidateSession(applicationId);
      setData(d);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setData(null);
      } else {
        setError(e instanceof Error ? e.message : "Не удалось загрузить данные");
        setData(null);
      }
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    if (!isActive) return;
    void load();
  }, [isActive, load]);

  useEffect(() => {
    if (!isActive) return;
    const id = setInterval(() => void load(), 60_000);
    return () => clearInterval(id);
  }, [isActive, load]);

  if (!isActive) return null;

  const regularWeight = 350 as const;

  const labelStyle: CSSProperties = {
    margin: 0,
    fontSize: 14,
    lineHeight: "14px",
    color: "#626262",
    fontWeight: regularWeight,
  };
  const questionTextStyle: CSSProperties = {
    margin: "8px 0 0",
    fontSize: 14,
    lineHeight: 1.4,
    color: "#626262",
    fontWeight: regularWeight,
  };
  const answerTextStyle: CSSProperties = {
    margin: "8px 0 0",
    fontSize: 16,
    lineHeight: 1.4,
    color: "#262626",
    fontWeight: regularWeight,
  };

  if (loading) {
    return <p style={{ margin: 0, fontSize: 14, fontWeight: regularWeight, color: "#626262" }}>Загрузка…</p>;
  }

  if (error) {
    return <p style={{ margin: 0, fontSize: 14, fontWeight: regularWeight, color: "#c62828" }}>{error}</p>;
  }

  if (!data?.interviewCompletedAt) {
    return (
      <p style={{ margin: 0, fontSize: 14, lineHeight: 1.4, fontWeight: regularWeight, color: "#626262" }}>
        Кандидат ещё не завершил AI-собеседование. После завершения здесь появятся вопросы и ответы.
      </p>
    );
  }

  return (
    <div style={{ display: "grid", gap: 0, fontSize: 14 }}>
      <header style={{ paddingBottom: 16 }}>
        <h3
          style={{
            margin: 0,
            fontSize: 20,
            lineHeight: "20px",
            fontWeight: 600,
            color: "#262626",
            letterSpacing: "-0.6px",
          }}
        >
          Итоги AI-собеседования
        </h3>
        <p style={{ ...labelStyle, marginTop: 8 }}>
          Завершено: {formatDateTimeForPanel(data.interviewCompletedAt, candidateFullName)}
        </p>
        {data.resolutionSummary ? (
          <p style={{ ...labelStyle, marginTop: 4 }}>
            Уверенность сводки: {resolutionConfidenceLabel(data.resolutionSummary.confidence)}
          </p>
        ) : null}
        <div
          role="separator"
          style={{
            marginTop: 16,
            height: 1,
            background: "#e1e1e1",
            border: 0,
          }}
        />
      </header>

      {data.resolutionSummaryError && !data.resolutionSummary ? (
        <div style={{ margin: "0 0 16px", display: "grid", gap: 6 }}>
          <p style={{ margin: 0, fontSize: 14, fontWeight: regularWeight, color: "#626262" }}>
            Автоматическая сводка не сформирована. Ниже — вопросы и ответы кандидата.
          </p>
          <p style={{ margin: 0, fontSize: 14, fontWeight: regularWeight, color: "#c62828" }}>
            {data.resolutionSummaryError}
          </p>
        </div>
      ) : null}
      {!data.resolutionSummary && !data.resolutionSummaryError ? (
        <p style={{ margin: "0 0 16px", fontSize: 14, fontWeight: regularWeight, color: "#626262" }}>
          Сводка формируется. Обновите страницу через несколько секунд.
        </p>
      ) : null}

      {data.resolutionSummary ? (
        <div style={{ display: "grid", gap: 16, marginBottom: 24 }}>
          <div>
            <p style={{ ...labelStyle, marginBottom: 4 }}>Краткий итог</p>
            <p style={{ ...answerTextStyle, margin: 0, whiteSpace: "pre-wrap" }}>
              {data.resolutionSummary.shortSummary}
            </p>
          </div>
          <div>
            <p style={{ ...labelStyle, marginBottom: 4 }}>Что удалось уточнить</p>
            {data.resolutionSummary.resolvedPoints.length === 0 ? (
              <p style={{ ...labelStyle, margin: 0 }}>—</p>
            ) : (
              <ul style={{ margin: 0, paddingLeft: 20, color: "#262626", fontWeight: regularWeight, lineHeight: 1.4 }}>
                {data.resolutionSummary.resolvedPoints.map((line, i) => (
                  <li key={`r-${i}`}>{line}</li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <p style={{ ...labelStyle, marginBottom: 4 }}>Что остаётся под вопросом</p>
            {data.resolutionSummary.unresolvedPoints.length === 0 ? (
              <p style={{ ...labelStyle, margin: 0 }}>—</p>
            ) : (
              <ul style={{ margin: 0, paddingLeft: 20, color: "#262626", fontWeight: regularWeight, lineHeight: 1.4 }}>
                {data.resolutionSummary.unresolvedPoints.map((line, i) => (
                  <li key={`u-${i}`}>{line}</li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <p style={{ ...labelStyle, marginBottom: 4 }}>Новая информация</p>
            {data.resolutionSummary.newInformation.length === 0 ? (
              <p style={{ ...labelStyle, margin: 0 }}>—</p>
            ) : (
              <ul style={{ margin: 0, paddingLeft: 20, color: "#262626", fontWeight: regularWeight, lineHeight: 1.4 }}>
                {data.resolutionSummary.newInformation.map((line, i) => (
                  <li key={`n-${i}`}>{line}</li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <p style={{ ...labelStyle, marginBottom: 4 }}>На что обратить внимание на живом собеседовании</p>
            {(data.resolutionSummary.followUpFocus ?? []).length === 0 ? (
              data.resolutionSummary.unresolvedPoints.length === 0 ? (
                <p style={{ ...labelStyle, margin: 0 }}>—</p>
              ) : (
                <ul style={{ margin: 0, paddingLeft: 20, color: "#262626", fontWeight: regularWeight, lineHeight: 1.4 }}>
                  {data.resolutionSummary.unresolvedPoints.slice(0, 4).map((line, i) => (
                    <li key={`f-der-${i}`}>Уточнить: {line}</li>
                  ))}
                </ul>
              )
            ) : (
              <ul style={{ margin: 0, paddingLeft: 20, color: "#262626", fontWeight: regularWeight, lineHeight: 1.4 }}>
                {(data.resolutionSummary.followUpFocus ?? []).map((line, i) => (
                  <li key={`f-${i}`}>{line}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      ) : null}

      <div style={{ display: "grid", gap: 24 }}>
        {data.questionsAndAnswers.map((row) => (
          <article key={`${row.order}-${row.questionId}`} style={{ margin: 0 }}>
            <p style={labelStyle}>Вопрос</p>
            <p style={questionTextStyle}>{row.questionText}</p>
            <p style={{ ...labelStyle, marginTop: 16 }}>Ответ</p>
            <p style={{ ...answerTextStyle, whiteSpace: "pre-wrap" }}>{row.answerText || "—"}</p>
          </article>
        ))}
      </div>
    </div>
  );
}
