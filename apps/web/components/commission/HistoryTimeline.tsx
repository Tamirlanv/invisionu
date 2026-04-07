"use client";

import Link from "next/link";
import { resolveDisplayDate } from "@/lib/commission/candidate-timestamp-override";
import type { CommissionHistoryEvent } from "@/lib/commission/types";

type Props = {
  items: CommissionHistoryEvent[];
  loading?: boolean;
  emptyText?: string;
  compact?: boolean;
  linkToCandidate?: boolean;
};

function formatTimestampRu(iso: string, candidateFullName: string): string {
  const dt = resolveDisplayDate(iso, candidateFullName);
  if (!dt) return iso;
  return dt.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function categoryColor(category: CommissionHistoryEvent["eventCategory"]): string {
  if (category === "commission") return "#4facea";
  if (category === "candidate") return "#98da00";
  return "#bdbdbd";
}

export function HistoryTimeline({
  items,
  loading = false,
  emptyText = "События пока отсутствуют.",
  compact = false,
  linkToCandidate = true,
}: Props) {
  if (loading) {
    return <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#626262" }}>Загрузка...</p>;
  }

  if (items.length === 0) {
    return <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#626262" }}>{emptyText}</p>;
  }

  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: compact ? 8 : 12 }}>
      {items.map((event) => {
        const href = `/commission/applications/${event.applicationId}?sidebar=history`;
        const body = (
          <>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
                flexWrap: "wrap",
                rowGap: 6,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", minWidth: 0 }}>
                <span style={{ fontSize: 12, fontWeight: 350, color: "#8b8b8b", letterSpacing: "-0.36px" }}>
                  {formatTimestampRu(event.timestamp, event.candidateFullName)}
                </span>
              </div>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 350,
                  color: "#8b8b8b",
                  letterSpacing: "-0.36px",
                  textAlign: "right",
                  flexShrink: 0,
                }}
              >
                {event.eventType}
              </span>
            </div>
            <p
              style={{
                margin: 0,
                fontSize: compact ? 13 : 14,
                fontWeight: 350,
                color: "#262626",
                letterSpacing: compact ? "-0.39px" : "-0.42px",
                lineHeight: compact ? "17px" : "18px",
              }}
            >
              {event.description}
            </p>
            <p
              style={{
                margin: 0,
                fontSize: 12,
                fontWeight: 350,
                color: "#8b8b8b",
                letterSpacing: "-0.36px",
              }}
            >
              Инициатор: {event.initiator}
            </p>
          </>
        );

        const accent = categoryColor(event.eventCategory);
        return (
          <li
            key={event.id}
            style={{
              border: "1px solid #ececec",
              borderLeft: `3px solid ${accent}`,
              borderRadius: 12,
              padding: compact ? "10px 12px" : "12px 14px",
              background: "#fff",
              display: "grid",
              gap: 6,
            }}
          >
            {linkToCandidate ? (
              <Link href={href} style={{ textDecoration: "none", display: "grid", gap: 6 }}>
                {body}
              </Link>
            ) : (
              <div style={{ display: "grid", gap: 6 }}>{body}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
