"use client";

import { useState } from "react";
import type { CommissionPermissions } from "@/lib/commission/permissions";
import type { CommissionApplicationDetailView } from "@/lib/commission/types";
import { moveApplicationToNextStage, setFinalDecision, updateStageStatus } from "@/lib/commission/query";

type Props = {
  detail: CommissionApplicationDetailView;
  permissions: CommissionPermissions;
  onChanged: () => Promise<void>;
  onError: (msg: string) => void;
};

export function ActionPanel({ detail, permissions, onChanged, onError }: Props) {
  const [pending, setPending] = useState(false);
  const [reason, setReason] = useState("");

  async function withAction(fn: () => Promise<void>) {
    setPending(true);
    try {
      await fn();
      setReason("");
      await onChanged();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Не удалось выполнить действие");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="card" style={{ display: "grid", gap: 10 }}>
      <h3 style={{ margin: 0 }}>Действия комиссии</h3>
      <textarea
        className="input"
        placeholder="Комментарий/обоснование (обязательно для некоторых действий)"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      />
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {permissions.canSetStageStatus
          ? (["new", "in_review", "needs_attention", "approved", "rejected"] as const).map((s) => (
              <button key={s} className="btn secondary" type="button" disabled={pending} onClick={() => void withAction(() => updateStageStatus(detail.application_id, s, reason))}>
                status: {s}
              </button>
            ))
          : null}
        {permissions.canMove && detail.stage.availableNextActions.includes("advance_stage") ? (
          <button className="btn" type="button" disabled={pending} onClick={() => void withAction(() => moveApplicationToNextStage(detail.application_id, reason))}>
            Перевести на следующий этап
          </button>
        ) : null}
      </div>
      {permissions.canSetFinalDecision ? (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {(["move_forward", "reject", "waitlist", "invite_interview", "enrolled"] as const).map((d) => (
            <button key={d} className="btn secondary" type="button" disabled={pending} onClick={() => void withAction(() => setFinalDecision(detail.application_id, d, reason))}>
              decision: {d}
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}

