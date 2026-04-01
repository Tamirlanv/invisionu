"use client";

import Link from "next/link";
import { useState } from "react";
import { CSS } from "@dnd-kit/utilities";
import { useSortable } from "@dnd-kit/sortable";
import type { CommissionBoardApplicationCard } from "@/lib/commission/types";
import type { CommissionPermissions } from "@/lib/commission/permissions";

type Props = {
  card: CommissionBoardApplicationCard;
  permissions: CommissionPermissions;
  isMoving: boolean;
  onQuickComment: (applicationId: string, body: string) => Promise<void>;
  onToggleAttention: (applicationId: string, value: boolean) => Promise<void>;
};

function borderByState(v: CommissionBoardApplicationCard["visualState"]): string {
  if (v === "positive") return "2px solid #98da00";
  if (v === "negative") return "2px solid #ef4444";
  if (v === "attention") return "2px solid #f59e0b";
  return "1px solid #f1f1f1";
}

export function ApplicationCard({ card, permissions, isMoving, onQuickComment, onToggleAttention }: Props) {
  const [comment, setComment] = useState("");
  const [pending, setPending] = useState(false);

  async function submitComment() {
    const text = comment.trim();
    if (!text) return;
    setPending(true);
    try {
      await onQuickComment(card.applicationId, text);
      setComment("");
    } finally {
      setPending(false);
    }
  }

  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({
    id: card.applicationId,
    disabled: !permissions.canMove || isMoving,
    data: { stage: card.currentStage },
  });

  return (
    <article
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      style={{
        border: borderByState(card.visualState),
        borderRadius: 16,
        padding: "16px 18px",
        background: "#fff",
        opacity: isMoving ? 0.6 : 1,
        display: "grid",
        gap: 10,
        transform: CSS.Transform.toString(transform),
        transition,
      }}
    >
      <div style={{ display: "grid", gap: 6 }}>
        <Link href={`/commission/applications/${card.applicationId}`} style={{ color: "#262626", fontWeight: 550, fontSize: 16 }}>
          {card.candidateFullName || "Кандидат"}
        </Link>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 14, color: "#626262" }}>
          <div>
            <p style={{ margin: 0 }}>{card.program || "—"}</p>
            <p style={{ margin: "4px 0 0" }}>{card.age ?? "—"} лет</p>
          </div>
          <div style={{ textAlign: "right" }}>
            <p style={{ margin: 0 }}>{card.submittedAt ? new Date(card.submittedAt).toLocaleDateString("ru-RU") : "—"}</p>
            <p style={{ margin: "4px 0 0" }}>{card.city || "—"}</p>
          </div>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span className="muted" style={{ fontSize: 13 }}>
          Комментарии: {card.commentCount}
        </span>
        {permissions.canSetAttention ? (
          <button
            className="btn secondary"
            type="button"
            onClick={() => void onToggleAttention(card.applicationId, !card.manualAttentionFlag)}
            style={{ padding: "6px 10px", fontSize: 12 }}
          >
            {card.manualAttentionFlag ? "Снять attention" : "Attention"}
          </button>
        ) : null}
      </div>

      {permissions.canComment ? (
        <div style={{ display: "flex", gap: 8 }}>
          <input
            className="input"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Быстрый комментарий"
          />
          <button className="btn secondary" type="button" onClick={() => void submitComment()} disabled={pending}>
            {pending ? "..." : "OK"}
          </button>
        </div>
      ) : null}
    </article>
  );
}

