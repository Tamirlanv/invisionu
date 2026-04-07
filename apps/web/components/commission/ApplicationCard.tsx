"use client";

import type { CSSProperties } from "react";
import Link from "next/link";
import { CSS } from "@dnd-kit/utilities";
import { useSortable } from "@dnd-kit/sortable";
import { getCommissionCardBorderStyle, getDataCheckPhaseCaption } from "@/lib/commission/cardBorder";
import { formatDateDDMMYY, resolveDisplayDate } from "@/lib/commission/candidate-timestamp-override";
import type { CommissionBoardApplicationCard, CommissionStage } from "@/lib/commission/types";
import type { CommissionPermissions } from "@/lib/commission/permissions";
import styles from "./ApplicationCard.module.css";

type Props = {
  card: CommissionBoardApplicationCard;
  columnStage: CommissionStage;
  permissions: CommissionPermissions;
  isMoving: boolean;
  onQuickComment: (applicationId: string, body: string) => Promise<void>;
  onToggleAttention: (applicationId: string, value: boolean) => Promise<void>;
};

function formatProgramLabel(raw: string | null | undefined): string {
  if (!raw) return "";
  const t = raw.trim();
  if (t === "Бакалавриат") return "Бакалавр";
  return t;
}

function formatDate(raw: string | null | undefined, candidateFullName: string): string {
  const d = resolveDisplayDate(raw, candidateFullName);
  if (!d) return raw ?? "—";
  return formatDateDDMMYY(d);
}

function DragHandleGrip() {
  return (
    <svg width="14" height="18" viewBox="0 0 14 18" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
      <circle cx="4" cy="4" r="1.5" fill="#626262" />
      <circle cx="10" cy="4" r="1.5" fill="#626262" />
      <circle cx="4" cy="9" r="1.5" fill="#626262" />
      <circle cx="10" cy="9" r="1.5" fill="#626262" />
      <circle cx="4" cy="14" r="1.5" fill="#626262" />
      <circle cx="10" cy="14" r="1.5" fill="#626262" />
    </svg>
  );
}

const articleBaseStyle: CSSProperties = {
  width: 278,
  minHeight: 88,
  borderRadius: 16,
  background: "#fff",
  display: "flex",
  flexDirection: "row",
  alignItems: "stretch",
  padding: 0,
  boxSizing: "border-box",
  overflow: "hidden",
};

function CardTextBlock({
  card,
  columnStage,
}: {
  card: CommissionBoardApplicationCard;
  columnStage: CommissionStage;
}) {
  const dataCheckCaption = columnStage === "data_check" ? getDataCheckPhaseCaption(card.dataCheckRunStatus) : null;
  const showApplicationReviewTotal =
    columnStage === "application_review" &&
    card.rubricThreeSectionsComplete &&
    typeof card.applicationReviewTotalScore === "number";

  return (
    <>
      <span
        style={{
          flexShrink: 0,
          fontSize: 16,
          fontWeight: 450,
          color: "#262626",
          letterSpacing: "-0.48px",
          lineHeight: "20px",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {card.candidateFullName || "Кандидат"}
      </span>
      {dataCheckCaption ? (
        <span
          style={{
            fontSize: 12,
            fontWeight: 400,
            color: "#626262",
            lineHeight: "14px",
            letterSpacing: "-0.36px",
          }}
        >
          {dataCheckCaption}
        </span>
      ) : null}

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          flexShrink: 0,
          fontSize: 14,
          fontWeight: 350,
          color: "#626262",
          letterSpacing: "-0.42px",
          lineHeight: "14px",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {card.program ? <span>{formatProgramLabel(card.program)}</span> : null}
          {card.age != null ? <span>{card.age} лет</span> : null}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 4, alignItems: "flex-end" }}>
          <span>{formatDate(card.submittedAt, card.candidateFullName)}</span>
          {card.city ? <span>{card.city}</span> : null}
        </div>
      </div>

      {showApplicationReviewTotal ? (
        <span
          style={{
            alignSelf: "center",
            fontSize: 14,
            fontWeight: 350,
            color: "#626262",
            letterSpacing: "-0.42px",
            lineHeight: "14px",
            marginTop: 4,
          }}
        >
          Итого: {Math.round(card.applicationReviewTotalScore!)}
        </span>
      ) : null}
    </>
  );
}

/** Статичная копия карточки для DragOverlay (портал вне overflow колонок/скролла). */
export function ApplicationCardDragOverlay({
  card,
  columnStage,
  showHandle,
}: {
  card: CommissionBoardApplicationCard;
  columnStage: CommissionStage;
  showHandle: boolean;
}) {
  return (
    <article
      className={`${styles.root} ${styles.overlayFace}`}
      style={{
        ...articleBaseStyle,
        border: getCommissionCardBorderStyle(columnStage, card),
        boxShadow: "0 12px 28px rgba(0,0,0,0.18)",
        cursor: "grabbing",
      }}
    >
      {showHandle ? (
        <div className={`${styles.handleRail} ${styles.handleRailOverlay}`}>
          <div className={`${styles.dragHandleBtn} ${styles.dragHandleBtnGrabbing}`} aria-hidden>
            <DragHandleGrip />
          </div>
        </div>
      ) : null}

      {showHandle ? (
        <div className={styles.cardLinkWithHandle} style={overlayLinkStyle}>
          <CardTextBlock card={card} columnStage={columnStage} />
        </div>
      ) : (
        <div className={styles.cardLinkNoHandle} style={overlayLinkStyle}>
          <CardTextBlock card={card} columnStage={columnStage} />
        </div>
      )}
    </article>
  );
}

const overlayLinkStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 8,
  flex: 1,
  minWidth: 0,
  boxSizing: "border-box",
};

export function ApplicationCard({ card, columnStage, permissions, isMoving }: Props) {
  const isOrangeDataCheckCard =
    columnStage === "data_check" &&
    (card.dataCheckRunStatus === "partial" || card.dataCheckRunStatus === "failed");
  const canDragCard = columnStage !== "data_check" || isOrangeDataCheckCard;
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: card.applicationId,
    disabled: !permissions.canMove || isMoving || !canDragCard,
    data: { stage: card.currentStage },
  });

  const href = `/commission/applications/${card.applicationId}`;
  const showHandle = permissions.canMove && !isMoving && canDragCard;

  return (
    <article
      ref={setNodeRef}
      className={`${styles.root} ${showHandle && isDragging ? styles.rootDragging : ""}`}
      style={{
        ...articleBaseStyle,
        border: getCommissionCardBorderStyle(columnStage, card),
        opacity: isMoving ? 0.6 : isDragging ? 0 : 1,
        pointerEvents: isDragging ? "none" : undefined,
        transform: CSS.Transform.toString(transform),
        transition,
      }}
    >
      {showHandle ? (
        <div className={styles.handleRail}>
          <button
            type="button"
            ref={setActivatorNodeRef}
            {...listeners}
            {...attributes}
            aria-label="Переместить карточку"
            className={`${styles.dragHandleBtn} ${isDragging ? styles.dragHandleBtnGrabbing : styles.dragHandleBtnGrab}`}
          >
            <DragHandleGrip />
          </button>
        </div>
      ) : null}

      <Link
        href={href}
        className={showHandle ? styles.cardLinkWithHandle : styles.cardLinkNoHandle}
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 8,
          flex: 1,
          minWidth: 0,
          boxSizing: "border-box",
          textDecoration: "none",
          color: "inherit",
          cursor: "pointer",
        }}
      >
        <CardTextBlock card={card} columnStage={columnStage} />
      </Link>
    </article>
  );
}
