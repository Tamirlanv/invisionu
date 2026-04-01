"use client";

import type { CommissionBoardMetrics } from "@/lib/commission/types";

export function MetricsRow({ metrics }: { metrics: CommissionBoardMetrics }) {
  const items = [
    { label: "Всего заявок", value: metrics.totalApplications },
    { label: "За сегодня", value: metrics.todayApplications },
    { label: "Требуют внимания", value: metrics.needsAttention },
    { label: "AI рекомендация", value: metrics.aiRecommended },
  ];
  return (
    <section style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))" }}>
      {items.map((i) => (
        <article
          key={i.label}
          className="card"
          style={{ padding: 20, borderRadius: 16, border: "1px solid #f1f1f1", boxShadow: "none" }}
        >
          <p style={{ margin: 0, fontSize: 20, fontWeight: 550, color: "#262626" }}>
            {i.label}
          </p>
          <p style={{ margin: "10px 0 0", fontSize: 42, lineHeight: "42px", fontWeight: 600, color: "#98da00" }}>
            {i.value}
          </p>
        </article>
      ))}
    </section>
  );
}

