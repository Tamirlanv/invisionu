"use client";

import type { CommissionApplicationDetailView } from "@/lib/commission/types";

export function CandidateSummaryCard({ detail }: { detail: CommissionApplicationDetailView }) {
  return (
    <section className="card" style={{ display: "grid", gap: 8 }}>
      <h2 style={{ margin: 0, fontSize: 18 }}>{detail.candidate.full_name || "Кандидат"}</h2>
      <p className="muted" style={{ margin: 0 }}>
        Программа: {detail.candidate.program ?? "—"}
      </p>
      <p className="muted" style={{ margin: 0 }}>
        Телефон: {detail.candidate.phone ?? "—"}
      </p>
      <p className="muted" style={{ margin: 0 }}>
        Город: {detail.candidate.city ?? "—"}
      </p>
      <p className="muted" style={{ margin: 0 }}>
        Возраст: {detail.candidate.age ?? "—"}
      </p>
      <p className="muted" style={{ margin: 0 }}>
        Application ID: {detail.application_id}
      </p>
      <p className="muted" style={{ margin: 0 }}>
        Этап: {detail.stage.currentStage}
      </p>
      <p className="muted" style={{ margin: 0 }}>
        Статус: {detail.stage.currentStageStatus}
      </p>
      <p className="muted" style={{ margin: 0 }}>
        Решение: {detail.stage.finalDecision ?? "—"}
      </p>
    </section>
  );
}

