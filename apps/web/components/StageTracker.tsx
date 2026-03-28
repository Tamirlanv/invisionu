"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";
import { applicationStageRu } from "@/lib/labels";

const ORDER = [
  "application",
  "initial_screening",
  "application_review",
  "interview",
  "committee_review",
  "decision",
];

type Status = {
  current_stage: string;
  stage_history: {
    to_stage: string;
    entered_at: string;
    candidate_visible_note?: string | null;
  }[];
  stage_descriptions: Record<string, string>;
  submission_state: { state: string; submitted_at: string | null; locked: boolean };
};

export function StageTracker() {
  const [data, setData] = useState<Status | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    async function run() {
      try {
        const s = await apiFetch<Status>("/candidates/me/application/status");
        setData(s);
      } catch (e) {
        if (e instanceof ApiError) {
          setErr(e.message);
        }
      }
    }
    void run();
  }, []);

  if (err) {
    return (
      <div className="card">
        <p className="error">{err}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="card">
        <p className="muted">Загрузка этапов…</p>
      </div>
    );
  }

  const currentIdx = Math.max(0, ORDER.indexOf(data.current_stage));

  return (
    <div className="card grid">
      <h2 className="h2">Этапы</h2>
      <p className="muted" style={{ margin: 0 }}>
        Подана: {data.submission_state.submitted_at || "—"} · Редактирование{" "}
        {data.submission_state.locked ? "закрыто" : "открыто"}
      </p>
      <ol style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 10 }}>
        {ORDER.map((stage, i) => {
          const done = i < currentIdx;
          const active = i === currentIdx;
          return (
            <li key={stage} style={{ opacity: active ? 1 : done ? 0.85 : 0.45 }}>
              <strong>{applicationStageRu(stage)}</strong>
              {active && <span> — текущий</span>}
              {done && !active && <span> — пройден</span>}
              {!done && !active && <span> — впереди</span>}
              <div className="muted" style={{ fontSize: 13 }}>
                {data.stage_descriptions[stage] || ""}
              </div>
            </li>
          );
        })}
      </ol>
      {data.stage_history.length > 0 && (
        <div>
          <h3 className="h2" style={{ fontSize: 15 }}>
            История
          </h3>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {data.stage_history.map((h) => (
              <li key={`${h.entered_at}-${h.to_stage}`}>
                <span className="muted">{h.entered_at}</span> → {applicationStageRu(h.to_stage)}
                {h.candidate_visible_note && <div className="muted">{h.candidate_visible_note}</div>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
