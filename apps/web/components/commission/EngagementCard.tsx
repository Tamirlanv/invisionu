"use client";

import Link from "next/link";
import { formatDateTimeDDMMYYHHMM, isTargetCandidateName, resolveDisplayDate } from "@/lib/commission/candidate-timestamp-override";
import type { CommissionEngagementCard } from "@/lib/commission/types";

type Props = {
  card: CommissionEngagementCard;
};

function engagementLabel(v: CommissionEngagementCard["engagementLevel"]): string {
  if (v === "High") return "Высокая";
  if (v === "Low") return "Низкая";
  return "Средняя";
}

function stageLabel(v: string | null): string {
  if (!v) return "—";
  const stage = String(v);
  if (stage === "data_check" || stage === "initial_screening") return "Проверка данных";
  if (stage === "application_review") return "Оценка заявки";
  if (stage === "interview") return "Собеседование";
  if (stage === "committee_review") return "Решение комиссии";
  if (stage === "decision") return "Результат";
  if (stage === "committee_decision") return "Решение комиссии";
  if (stage === "result") return "Результат";
  return stage;
}

function riskTone(v: CommissionEngagementCard["riskLevel"]): string {
  if (v === "High") return "#f4511e";
  if (v === "Low") return "#98da00";
  return "#dacf00";
}

export function EngagementCard({ card }: Props) {
  const tone = riskTone(card.riskLevel);
  const displayLastActivity = (() => {
    if (!isTargetCandidateName(card.candidateFullName)) return card.lastActivityHumanized || "нет данных";
    const d = resolveDisplayDate(card.lastActivityAtIso, card.candidateFullName);
    if (!d) return card.lastActivityHumanized || "нет данных";
    return formatDateTimeDDMMYYHHMM(d);
  })();

  return (
    <article
      style={{
        width: "100%",
        border: `2px solid ${tone}`,
        borderRadius: 16,
        background: "#ffffff",
        boxShadow: "none",
        padding: "16px 24px",
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <Link
        href={`/commission/applications/${card.applicationId}?sidebar=engagement`}
        style={{
          fontSize: 16,
          fontWeight: 450,
          color: "#262626",
          letterSpacing: "-0.48px",
          lineHeight: "16px",
          textDecoration: "none",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {card.candidateFullName || "Кандидат"}
      </Link>

      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 12,
          width: "100%",
          fontSize: 14,
          fontWeight: 350,
          letterSpacing: "-0.42px",
          lineHeight: "14px",
          color: "#626262",
        }}
      >
        <p style={{ margin: 0, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {card.program || "—"}
        </p>
        <p style={{ margin: 0, whiteSpace: "nowrap", textAlign: "right" }}>
          {displayLastActivity}
        </p>
      </div>

      <div style={{ display: "grid", gap: 8 }}>
        <p
          style={{
            margin: 0,
            fontSize: 14,
            fontWeight: 350,
            letterSpacing: "-0.42px",
            lineHeight: "14px",
            color: "#626262",
            whiteSpace: "nowrap",
          }}
        >
          <span>Вовлеченность:</span>
          <span style={{ color: "#262626" }}>{` ${engagementLabel(card.engagementLevel)}`}</span>
        </p>
        <p
          style={{
            margin: 0,
            fontSize: 14,
            fontWeight: 350,
            letterSpacing: "-0.42px",
            lineHeight: "14px",
            color: "#626262",
            whiteSpace: "nowrap",
          }}
        >
          <span>На платформе:</span>
          <span style={{ color: "#262626" }}>{` ${card.activeTimeHumanized ?? "нет данных"}`}</span>
        </p>
        <p
          style={{
            margin: 0,
            fontSize: 14,
            fontWeight: 350,
            letterSpacing: "-0.42px",
            lineHeight: "14px",
            color: "#626262",
            whiteSpace: "nowrap",
          }}
        >
          <span>Этап:</span>
          <span style={{ color: "#262626" }}>{` ${stageLabel(card.currentStage)}`}</span>
        </p>
      </div>
    </article>
  );
}
