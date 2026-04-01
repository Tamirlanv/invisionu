"use client";

import { useEffect, useMemo, useState } from "react";
import { DndContext, type DragEndEvent, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { COMMISSION_STAGE_ORDER, COMMISSION_STAGE_TITLES } from "@/lib/commission/constants";
import { isNextStageOnly } from "@/lib/commission/dnd";
import { permissionsFromRole } from "@/lib/commission/permissions";
import {
  createQuickComment,
  getCommissionBoard,
  getCommissionRole,
  moveApplicationToNextStage,
  setAttentionFlag,
} from "@/lib/commission/query";
import { startPollingUpdates } from "@/lib/commission/revalidate";
import type { CommissionBoardFilters, CommissionBoardResponse, CommissionRole, CommissionStage } from "@/lib/commission/types";
import { BoardColumn } from "./BoardColumn";

type Props = {
  filters: CommissionBoardFilters;
  onError: (msg: string) => void;
};

const MAIN_BOARD_STAGES: CommissionStage[] = COMMISSION_STAGE_ORDER.filter((s) => s !== "result");

export function BoardContainer({ filters, onError }: Props) {
  const [role, setRole] = useState<CommissionRole | null>(null);
  const [data, setData] = useState<CommissionBoardResponse | null>(null);
  const [movingId, setMovingId] = useState<string | null>(null);

  const permissions = useMemo(() => permissionsFromRole(role), [role]);
  const sensors = useSensors(useSensor(PointerSensor));

  async function refresh() {
    try {
      const [r, d] = await Promise.all([getCommissionRole(), getCommissionBoard(filters)]);
      setRole(r);
      setData(d);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Не удалось загрузить board");
    }
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.search, filters.program, filters.range]);

  useEffect(() => {
    const stop = startPollingUpdates(() => {
      void refresh();
    });
    return stop;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.search, filters.program, filters.range]);

  async function onDropCard(applicationId: string, toStage: CommissionStage) {
    if (!permissions.canMove || !data) return;
    const from = data.columns.find((c) => c.applications.some((a) => a.applicationId === applicationId));
    if (!from) return;
    if (!isNextStageOnly(from.stage, toStage)) {
      onError("Можно перемещать только на следующий этап.");
      return;
    }
    const snapshot = data;
    setMovingId(applicationId);
    setData((prev) => {
      if (!prev) return prev;
      const next = structuredClone(prev) as CommissionBoardResponse;
      const src = next.columns.find((c) => c.stage === from.stage);
      const dst = next.columns.find((c) => c.stage === toStage);
      if (!src || !dst) return prev;
      const idx = src.applications.findIndex((a) => a.applicationId === applicationId);
      if (idx < 0) return prev;
      const [card] = src.applications.splice(idx, 1);
      card.currentStage = toStage;
      dst.applications.unshift(card);
      return next;
    });
    try {
      await moveApplicationToNextStage(applicationId);
      await refresh();
    } catch (e) {
      setData(snapshot);
      onError(e instanceof Error ? e.message : "Не удалось переместить заявку");
    } finally {
      setMovingId(null);
    }
  }

  function handleDragEnd(event: DragEndEvent) {
    const applicationId = String(event.active.id);
    const overId = event.over?.id ? String(event.over.id) : "";
    if (!overId.startsWith("column:")) return;
    const toStage = overId.replace("column:", "") as CommissionStage;
    void onDropCard(applicationId, toStage);
  }

  async function onQuickComment(applicationId: string, body: string) {
    try {
      await createQuickComment(applicationId, body);
      await refresh();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Не удалось добавить комментарий");
    }
  }

  async function onToggleAttention(applicationId: string, value: boolean) {
    try {
      await setAttentionFlag(applicationId, value);
      await refresh();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Не удалось обновить attention");
    }
  }

  if (!data) return <p className="muted">Загрузка доски…</p>;
  if (!permissions.canViewBoard) return <p className="error">Нет доступа к странице комиссии.</p>;

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      <section
        style={{
          display: "flex",
          gap: 20,
          overflowX: "auto",
          alignItems: "flex-start",
          paddingBottom: 12,
        }}
      >
        {MAIN_BOARD_STAGES.map((stage, idx) => {
          const col = data.columns.find((c) => c.stage === stage) ?? {
            stage,
            title: COMMISSION_STAGE_TITLES[stage],
            applications: [],
          };
          return (
            <SortableContext key={stage} items={col.applications.map((a) => a.applicationId)} strategy={verticalListSortingStrategy}>
              <BoardColumn
                order={idx + 1}
                stage={stage}
                title={col.title}
                cards={col.applications}
                permissions={permissions}
                movingId={movingId}
                onQuickComment={onQuickComment}
                onToggleAttention={onToggleAttention}
              />
            </SortableContext>
          );
        })}
      </section>
    </DndContext>
  );
}

