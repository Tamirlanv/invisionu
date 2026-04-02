"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { moveApplicationToNextStage } from "@/lib/commission/query";

type Props = {
  applicationId: string;
  canMoveForward: boolean;
};

export function MoveNextStageButton({ applicationId, canMoveForward }: Props) {
  const router = useRouter();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function onMove() {
    setError(null);
    startTransition(async () => {
      try {
        await moveApplicationToNextStage(applicationId, reason || undefined);
        setReason("");
        router.refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Не удалось перевести заявку на следующий этап");
      }
    });
  }

  if (!canMoveForward) return null;

  return (
    <div style={{ display: "grid", gap: 10, justifyItems: "center", paddingTop: 12 }}>
      <button
        type="button"
        onClick={onMove}
        disabled={isPending}
        style={{
          background: "#98da00",
          color: "#fff",
          border: "none",
          borderRadius: 8,
          padding: "12px 24px",
          fontSize: 14,
          letterSpacing: "-0.42px",
          lineHeight: "14px",
          cursor: isPending ? "not-allowed" : "pointer",
          opacity: isPending ? 0.6 : 1,
        }}
      >
        {isPending ? "Выполняется..." : "Далее"}
      </button>
      {error ? <p style={{ margin: 0, fontSize: 13, color: "#e53935" }}>{error}</p> : null}
    </div>
  );
}
