"use client";

import Link from "next/link";
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
  return "none";
}

function formatDate(raw: string | null | undefined): string {
  if (!raw) return "—";
  const d = new Date(raw);
  if (isNaN(d.getTime())) return raw;
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yy = String(d.getFullYear()).slice(-2);
  return `${dd}.${mm}.${yy}`;
}

export function ApplicationCard({ card, permissions, isMoving }: Props) {
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
        width: 278,
        height: 88,
        border: borderByState(card.visualState),
        borderRadius: 16,
        background: "#fff",
        opacity: isMoving ? 0.6 : 1,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        padding: "16px 24px",
        boxSizing: "border-box",
        transform: CSS.Transform.toString(transform),
        transition,
        cursor: permissions.canMove ? "grab" : "default",
        overflow: "hidden",
      }}
    >
      {/* Name */}
      <Link
        href={`/commission/applications/${card.applicationId}`}
        style={{
          fontSize: 16,
          fontWeight: 450,
          color: "#262626",
          letterSpacing: "-0.48px",
          lineHeight: "16px",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
          textDecoration: "none",
        }}
      >
        {card.candidateFullName || "Кандидат"}
      </Link>

      {/* Meta row */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          fontSize: 14,
          fontWeight: 350,
          color: "#626262",
          letterSpacing: "-0.42px",
          lineHeight: "14px",
        }}
      >
        {/* Left: program + age */}
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {card.program ? <span>{card.program}</span> : null}
          {card.age != null ? <span>{card.age} лет</span> : null}
        </div>

        {/* Right: date + city */}
        <div style={{ display: "flex", flexDirection: "column", gap: 4, alignItems: "flex-end" }}>
          <span>{formatDate(card.submittedAt)}</span>
          {card.city ? <span>{card.city}</span> : null}
        </div>
      </div>
    </article>
  );
}
