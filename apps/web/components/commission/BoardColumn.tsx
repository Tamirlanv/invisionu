"use client";

import { useDroppable } from "@dnd-kit/core";
import type { CommissionBoardApplicationCard, CommissionStage } from "@/lib/commission/types";
import type { CommissionPermissions } from "@/lib/commission/permissions";
import { ApplicationCard } from "./ApplicationCard";

type Props = {
  order: number;
  stage: CommissionStage;
  title: string;
  cards: CommissionBoardApplicationCard[];
  permissions: CommissionPermissions;
  movingId: string | null;
  onQuickComment: (applicationId: string, body: string) => Promise<void>;
  onToggleAttention: (applicationId: string, value: boolean) => Promise<void>;
};

export function BoardColumn({
  order,
  stage,
  title,
  cards,
  permissions,
  movingId,
  onQuickComment,
  onToggleAttention,
}: Props) {
  const { setNodeRef, isOver } = useDroppable({ id: `column:${stage}` });
  return (
    <section
      ref={setNodeRef}
      style={{
        minHeight: 280,
        border: isOver ? "1px solid #262626" : "1px solid #f1f1f1",
        borderRadius: 16,
        padding: 16,
        background: "#f1f1f1",
        display: "grid",
        gap: 16,
        width: 310,
        minWidth: 310,
        flex: "0 0 310px",
      }}
    >
      <header style={{ display: "flex", alignItems: "center", gap: 8, width: "100%", height: "fit-content" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 28, lineHeight: "20px", fontWeight: 600, color: "#98da00" }}>
            {String(order).padStart(2, "0")}
          </span>
          <h3 style={{ margin: 0, fontSize: 20, lineHeight: "20px", fontWeight: 550 }}>{title}</h3>
        </div>
        <span className="muted" style={{ fontSize: 12, lineHeight: "12px", marginLeft: "auto" }}>
          {cards.length}
        </span>
      </header>
      {cards.length === 0 ? <p className="muted">Нет заявок</p> : null}
      {cards.map((card) => (
        <ApplicationCard
          key={card.applicationId}
          card={card}
          permissions={permissions}
          isMoving={movingId === card.applicationId}
          onQuickComment={onQuickComment}
          onToggleAttention={onToggleAttention}
        />
      ))}
    </section>
  );
}

