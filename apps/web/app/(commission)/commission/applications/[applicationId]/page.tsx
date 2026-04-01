"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ActionPanel } from "@/components/commission/detail/ActionPanel";
import { ActivityPreview } from "@/components/commission/detail/ActivityPreview";
import { AISummaryCard } from "@/components/commission/detail/AISummaryCard";
import { ApplicationTabs } from "@/components/commission/detail/ApplicationTabs";
import { CandidateSummaryCard } from "@/components/commission/detail/CandidateSummaryCard";
import { CommentsPanel } from "@/components/commission/detail/CommentsPanel";
import { RubricPanel } from "@/components/commission/detail/RubricPanel";
import { StagePipeline } from "@/components/commission/detail/StagePipeline";
import { ApiError } from "@/lib/api-client";
import { getCommissionApplicationDetail, getCommissionRole } from "@/lib/commission/query";
import { permissionsFromRole } from "@/lib/commission/permissions";
import type { CommissionApplicationDetailView } from "@/lib/commission/types";
import styles from "./page.module.css";

export default function CommissionApplicationDetailPage() {
  const params = useParams();
  const applicationId = String(params.applicationId ?? "");

  const [detail, setDetail] = useState<CommissionApplicationDetailView | null>(null);
  const [role, setRole] = useState<Awaited<ReturnType<typeof getCommissionRole>>>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const permissions = useMemo(() => permissionsFromRole(role), [role]);

  const refresh = useCallback(async () => {
    setErr(null);
    try {
      const [d, r] = await Promise.all([getCommissionApplicationDetail(applicationId), getCommissionRole()]);
      setDetail(d);
      setRole(r);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setErr("Заявка не найдена.");
      } else if (e instanceof ApiError && e.status === 403) {
        setErr("Нет доступа к этой заявке.");
      } else {
        setErr(e instanceof Error ? e.message : "Не удалось загрузить заявку");
      }
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (loading) {
    return <p className="muted">Загрузка…</p>;
  }
  if (err || !detail) {
    return (
      <main className={styles.root}>
        <p className="error">{err ?? "Ошибка"}</p>
        <Link href="/commission">← К доске</Link>
      </main>
    );
  }

  return (
    <main className={styles.root}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
        <h1 className="h2" style={{ margin: 0 }}>
          Заявка кандидата
        </h1>
        <Link className="btn secondary" href="/commission">
          ← К доске
        </Link>
      </div>

      <StagePipeline currentStage={detail.stage.currentStage} />

      <div className={styles.grid}>
        <aside style={{ display: "grid", gap: 12 }}>
          <CandidateSummaryCard detail={detail} />
          <AISummaryCard ai={detail.aiSummary} />
        </aside>

        <div className={styles.main}>
          <ActionPanel detail={detail} permissions={permissions} onChanged={refresh} onError={setErr} />
          {err ? <p className="error">{err}</p> : null}
          <ApplicationTabs detail={detail} />
          <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit,minmax(280px,1fr))" }}>
            <CommentsPanel detail={detail} permissions={permissions} onChanged={refresh} onError={setErr} />
            <RubricPanel detail={detail} permissions={permissions} onChanged={refresh} onError={setErr} />
          </div>
          <ActivityPreview items={detail.recentActivity} />
        </div>
      </div>
    </main>
  );
}
