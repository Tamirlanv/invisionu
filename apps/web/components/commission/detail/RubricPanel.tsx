"use client";

import { useMemo, useState } from "react";
import type { CommissionPermissions } from "@/lib/commission/permissions";
import type { CommissionApplicationDetailView } from "@/lib/commission/types";
import { setInternalRecommendation, setRubricScores } from "@/lib/commission/query";

type Props = {
  detail: CommissionApplicationDetailView;
  permissions: CommissionPermissions;
  onChanged: () => Promise<void>;
  onError: (msg: string) => void;
};

const RUBRICS = ["motivation", "leadership", "maturity", "resilience", "mission_fit"] as const;
const SCORES = ["strong", "medium", "low"] as const;

export function RubricPanel({ detail, permissions, onChanged, onError }: Props) {
  const [pending, setPending] = useState(false);
  const [scores, setScores] = useState<Record<string, string>>(() => {
    const out: Record<string, string> = {};
    for (const r of RUBRICS) out[r] = "medium";
    return out;
  });
  const [internalRec, setInternalRec] = useState<string>("recommend_forward");
  const [reason, setReason] = useState("");

  const allScores = useMemo(() => detail.review.rubricScores, [detail.review.rubricScores]);

  async function saveRubric() {
    if (!permissions.canSetRubric) return;
    setPending(true);
    try {
      const items = RUBRICS.map((rubric) => ({ rubric, score: scores[rubric] ?? "medium" }));
      await setRubricScores(detail.application_id, items);
      await onChanged();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Не удалось сохранить рубрику");
    } finally {
      setPending(false);
    }
  }

  async function saveInternal() {
    if (!permissions.canSetInternalRecommendation) return;
    setPending(true);
    try {
      await setInternalRecommendation(detail.application_id, internalRec, reason);
      setReason("");
      await onChanged();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Не удалось сохранить рекомендацию");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="card" style={{ display: "grid", gap: 10 }}>
      <h3 style={{ margin: 0 }}>Ручные оценки</h3>
      <p className="muted" style={{ margin: 0 }}>
        Записей рубрики: {detail.review.rubricScores.length}
      </p>
      {permissions.canSetRubric ? (
        <div style={{ display: "grid", gap: 8 }}>
          {RUBRICS.map((r) => (
            <label key={r} style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span style={{ width: 120 }}>{r}</span>
              <select className="input" value={scores[r]} onChange={(e) => setScores((s) => ({ ...s, [r]: e.target.value }))}>
                {SCORES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
          ))}
          <button className="btn secondary" type="button" disabled={pending} onClick={() => void saveRubric()}>
            Сохранить мою рубрику
          </button>
        </div>
      ) : (
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {allScores.map((x) => (
            <li key={`${x.authorId}-${x.criterion}-${x.updatedAt}`}>
              {x.criterion}: {x.value} ({x.authorId})
            </li>
          ))}
        </ul>
      )}
      <div style={{ display: "grid", gap: 8 }}>
        <h4 style={{ margin: 0 }}>Внутренняя рекомендация</h4>
        {permissions.canSetInternalRecommendation ? (
          <>
            <select className="input" value={internalRec} onChange={(e) => setInternalRec(e.target.value)}>
              <option value="recommend_forward">recommend_forward</option>
              <option value="needs_discussion">needs_discussion</option>
              <option value="reject">reject</option>
            </select>
            <textarea className="input" placeholder="Комментарий (обязателен для reject)" value={reason} onChange={(e) => setReason(e.target.value)} />
            <button className="btn secondary" type="button" disabled={pending} onClick={() => void saveInternal()}>
              Сохранить рекомендацию
            </button>
          </>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {detail.review.internalRecommendations.map((r) => (
              <li key={`${r.authorId}-${r.updatedAt}`}>
                {r.recommendation} ({r.authorId})
              </li>
            ))}
          </ul>
        )}
      </div>
      {detail.review.tags.length ? (
        <p className="muted" style={{ margin: 0 }}>
          Теги заявки: {detail.review.tags.join(", ")}
        </p>
      ) : null}
    </section>
  );
}
