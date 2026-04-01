"use client";

import type { ApplicationAISummaryView } from "@/lib/commission/types";

export function AISummaryCard({ ai }: { ai: ApplicationAISummaryView | null }) {
  if (!ai || ai.status !== "ready") {
    return (
      <section className="card">
        <h3 style={{ marginTop: 0 }}>AI Summary</h3>
        <p className="muted">AI summary пока не сгенерирован.</p>
      </section>
    );
  }
  return (
    <section className="card" style={{ display: "grid", gap: 8 }}>
      <h3 style={{ margin: 0 }}>AI Summary</h3>
      <p className="muted" style={{ margin: 0 }}>
        Advisory-only: финальное решение принимает комиссия.
      </p>
      <p style={{ margin: 0 }}>{ai.summaryText ?? "—"}</p>
      <p className="muted" style={{ margin: 0 }}>
        Recommendation: {ai.recommendation ?? "—"} / Confidence: {ai.confidenceScore ?? "—"}
      </p>
      {ai.strengths.length ? <p style={{ margin: 0 }}>Сильные стороны: {ai.strengths.join(", ")}</p> : null}
      {ai.weakPoints.length ? <p style={{ margin: 0 }}>Зоны внимания: {ai.weakPoints.join(", ")}</p> : null}
      {ai.redFlags.length ? <p style={{ margin: 0 }}>Red flags: {ai.redFlags.join(", ")}</p> : null}
      {ai.explainabilityNotes.length ? <p style={{ margin: 0 }}>Explainability: {ai.explainabilityNotes.join(" · ")}</p> : null}
    </section>
  );
}

