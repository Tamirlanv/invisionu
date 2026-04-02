"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { CommissionCommentBlock } from "@/components/commission/detail/CommissionCommentBlock";
import { MoveNextStageButton } from "@/components/commission/detail/MoveNextStageButton";
import { PersonalInfoSection } from "@/components/commission/detail/PersonalInfoSection";
import { TestInfoSection } from "@/components/commission/detail/TestInfoSection";
import { ApiError } from "@/lib/api-client";
import { permissionsFromRole } from "@/lib/commission/permissions";
import {
  deleteCommissionApplication,
  getCommissionApplicationPersonalInfo,
  getCommissionApplicationTestInfo,
  getCommissionRole,
} from "@/lib/commission/query";
import type { CommissionApplicationPersonalInfoView, CommissionApplicationTestInfoView, CommissionRole } from "@/lib/commission/types";
import styles from "./page.module.css";

type LoadError = { status: number | null; message: string };

/** Formats an ISO date string or "YYYY-MM-DD" as "DD.MM.YY" */
function formatSubmittedDate(raw: string): string {
  const d = new Date(raw);
  if (isNaN(d.getTime())) return raw;
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yy = String(d.getFullYear()).slice(-2);
  return `${dd}.${mm}.${yy}`;
}

function ProcessingBanner({ data }: { data: CommissionApplicationPersonalInfoView }) {
  const ps = data.processingStatus;
  if (!ps || ps.overall === "ready") return null;

  const isError = ps.overall === "failed" || ps.manualReviewRequired;
  const label =
    ps.overall === "pending"
      ? "Ожидание обработки..."
      : ps.overall === "running"
        ? `Проверка данных: обработано ${ps.completedCount} из ${ps.totalCount}`
        : ps.overall === "partial"
          ? `Частично обработано (${ps.completedCount} из ${ps.totalCount})`
          : `Ошибка обработки (${ps.completedCount} из ${ps.totalCount})`;

  return (
    <div
      style={{
        display: "grid",
        gap: 6,
        padding: "12px 16px",
        borderRadius: 8,
        borderLeft: isError ? "4px solid #e53935" : "4px solid #fb8c00",
        background: isError ? "#fef2f2" : "#fff8e1",
      }}
    >
      <p style={{ margin: 0, fontSize: 14, fontWeight: 550 }}>
        {isError ? "Требуется внимание" : "Обработка заявки"}
      </p>
      <p style={{ margin: 0, fontSize: 14, color: "#626262" }}>{label}</p>
      {ps.warnings.length > 0 ? (
        <p style={{ margin: 0, fontSize: 13, color: "#626262" }}>{ps.warnings.join("; ")}</p>
      ) : null}
      {ps.errors.length > 0 ? (
        <p style={{ margin: 0, fontSize: 13, color: "#e53935" }}>{ps.errors.join("; ")}</p>
      ) : null}
    </div>
  );
}

export default function CommissionApplicationDetailPage() {
  const params = useParams<{ applicationId?: string | string[] }>();
  const applicationId = Array.isArray(params.applicationId) ? params.applicationId[0] : params.applicationId;
  const router = useRouter();
  const [data, setData] = useState<CommissionApplicationPersonalInfoView | null>(null);
  const [role, setRole] = useState<CommissionRole | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<LoadError | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const deleteRef = useRef(false);

  const [activeTab, setActiveTab] = useState("Личная информация");
  const [testData, setTestData] = useState<CommissionApplicationTestInfoView | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const testFetchedRef = useRef(false);

  async function handleDelete() {
    if (!applicationId || deleteRef.current) return;
    if (!confirm("Удалить заявку? Это действие необратимо.")) return;
    deleteRef.current = true;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteCommissionApplication(applicationId);
      router.push("/commission");
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : "Не удалось удалить заявку");
      deleteRef.current = false;
    } finally {
      setDeleting(false);
    }
  }

  useEffect(() => {
    if (!applicationId) {
      setLoading(false);
      setLoadError({ status: 404, message: "Заявка не найдена." });
      return;
    }
    let cancelled = false;
    async function load() {
      setLoading(true);
      setLoadError(null);
      try {
        const [detail, commissionRole] = await Promise.all([
          getCommissionApplicationPersonalInfo(applicationId),
          getCommissionRole(),
        ]);
        if (cancelled) return;
        setData(detail);
        setRole(commissionRole);
      } catch (error) {
        if (cancelled) return;
        if (error instanceof ApiError) {
          setLoadError({ status: error.status, message: error.message });
        } else {
          setLoadError({ status: null, message: "Не удалось загрузить заявку" });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [applicationId]);

  useEffect(() => {
    if (activeTab !== "Тест" || !applicationId || testFetchedRef.current) return;
    let cancelled = false;
    testFetchedRef.current = true;
    setTestLoading(true);
    getCommissionApplicationTestInfo(applicationId)
      .then((res) => {
        if (!cancelled) setTestData(res);
      })
      .catch(() => {
        testFetchedRef.current = false;
      })
      .finally(() => {
        if (!cancelled) setTestLoading(false);
      });
    return () => { cancelled = true; };
  }, [activeTab, applicationId]);

  const permissions = useMemo(() => permissionsFromRole(role), [role]);

  if (loading) {
    return (
      <main className={styles.root}>
        <p style={{ color: "#626262" }}>Загрузка заявки...</p>
      </main>
    );
  }

  if (loadError?.status === 404) {
    return (
      <main className={styles.root}>
        <p className="error">Заявка не найдена.</p>
        <Link href="/commission">← К доске</Link>
      </main>
    );
  }

  if (loadError?.status === 403) {
    return (
      <main className={styles.root}>
        <p className="error">Нет доступа к этой заявке.</p>
        <Link href="/commission">← К доске</Link>
      </main>
    );
  }

  if (loadError || !data) {
    return (
      <main className={styles.root}>
        <p className="error">{loadError?.message ?? "Не удалось загрузить заявку"}</p>
        <Link href="/commission">← К доске</Link>
      </main>
    );
  }

  const processingInProgress =
    data.processingStatus != null &&
    (data.processingStatus.overall === "pending" || data.processingStatus.overall === "running");

  return (
    <main className={styles.root}>
      <div className={styles.header}>
        <h1 className={styles.pageTitle}>Страница ученика</h1>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {permissions.canMove ? (
            <button
              type="button"
              onClick={() => void handleDelete()}
              disabled={deleting}
              style={{
                fontSize: 16,
                fontWeight: 350,
                color: "#e53935",
                background: "none",
                border: "none",
                cursor: deleting ? "not-allowed" : "pointer",
                padding: 0,
                opacity: deleting ? 0.5 : 1,
              }}
            >
              {deleting ? "Удаление..." : "Удалить"}
            </button>
          ) : null}
          {deleteError ? (
            <span style={{ fontSize: 13, color: "#e53935" }}>{deleteError}</span>
          ) : null}
          <Link href="/commission" style={{ fontSize: 14, color: "#626262", textDecoration: "none" }}>
            ← К доске
          </Link>
        </div>
      </div>

      <div className={styles.layout}>
        {/* ---- LEFT SIDEBAR ---- */}
        <aside className={styles.sidebar}>
          {/* Card 1: Candidate Info */}
          <section className={styles.sideCard}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
              <div style={{ display: "grid", gap: 6, minWidth: 0 }}>
                <h2 className={styles.candidateName} style={{ whiteSpace: "nowrap" }}>
                  {data.candidateSummary.fullName}
                </h2>
                {data.candidateSummary.program ? (
                  <p className={styles.candidateMeta}>{data.candidateSummary.program}</p>
                ) : null}
                {data.candidateSummary.phone ? (
                  <p className={styles.candidateMeta}>{data.candidateSummary.phone}</p>
                ) : null}
                {data.candidateSummary.telegram ? (
                  <p className={styles.candidateMeta}>tg: {data.candidateSummary.telegram}</p>
                ) : null}
              </div>
              {data.candidateSummary.submittedAt ? (
                <p className={styles.candidateDate}>
                  {formatSubmittedDate(data.candidateSummary.submittedAt)}
                </p>
              ) : null}
            </div>
          </section>

          {/* Card 2: AI Summary — swaps based on active tab */}
          <section className={styles.sideCard}>
            <h3 className={styles.aiTitle}>Summary</h3>
            {activeTab === "Тест" ? (
              testData?.aiSummary ? (
                <>
                  {testData.personalityProfile?.profileTitle ? (
                    <div className={styles.aiRow}>
                      <p className={styles.aiLabel}>Тип личности</p>
                      <p className={styles.aiLabel}>{testData.personalityProfile.profileTitle}</p>
                    </div>
                  ) : null}
                  <div style={{ display: "grid", gap: 4 }}>
                    <p className={styles.aiLabel}>О кандидате</p>
                    <p className={styles.aiText}>{testData.aiSummary.aboutCandidate ?? "—"}</p>
                  </div>
                  {testData.aiSummary.weakPoints.length > 0 ? (
                    <div style={{ display: "grid", gap: 4 }}>
                      <p className={styles.aiLabel}>Слабые места</p>
                      <p className={styles.aiText}>{testData.aiSummary.weakPoints.join(", ")}</p>
                    </div>
                  ) : null}
                </>
              ) : testLoading ? (
                <p className={styles.aiText}>Формируется...</p>
              ) : testData?.personalityProfile ? (
                <div style={{ display: "grid", gap: 4 }}>
                  <div className={styles.aiRow}>
                    <p className={styles.aiLabel}>Тип личности</p>
                    <p className={styles.aiLabel}>{testData.personalityProfile.profileTitle}</p>
                  </div>
                  <p className={styles.aiText}>{testData.personalityProfile.summary ?? "—"}</p>
                </div>
              ) : (
                <p className={styles.aiText}>Сводка теста пока отсутствует.</p>
              )
            ) : data.aiSummary ? (
              <>
                {data.aiSummary.profileTitle ? (
                  <div className={styles.aiRow}>
                    <p className={styles.aiLabel}>Тест</p>
                    <p className={styles.aiLabel}>{data.aiSummary.profileTitle}</p>
                  </div>
                ) : null}
                <div style={{ display: "grid", gap: 4 }}>
                  <p className={styles.aiLabel}>О кандидате</p>
                  <p className={styles.aiText}>{data.aiSummary.summaryText ?? "—"}</p>
                </div>
                {data.aiSummary.weakPoints.length > 0 ? (
                  <div style={{ display: "grid", gap: 4 }}>
                    <p className={styles.aiLabel}>Слабые места</p>
                    <p className={styles.aiText}>{data.aiSummary.weakPoints.join(", ")}</p>
                  </div>
                ) : null}
              </>
            ) : (
              <p className={styles.aiText}>
                {processingInProgress ? "Формируется..." : "Сводка пока отсутствует."}
              </p>
            )}
          </section>

          {/* Card 3: Comment */}
          <section className={styles.sideCard} style={{ gap: 12 }}>
            <CommissionCommentBlock
              applicationId={data.applicationId}
              comments={data.comments}
              canComment={permissions.canComment && data.actions.canComment}
              embedded
            />
          </section>
        </aside>

        {/* ---- RIGHT MAIN CONTENT ---- */}
        <div className={styles.main}>
          <ProcessingBanner data={data} />
          <PersonalInfoSection
            data={data}
            activeTab={activeTab}
            onTabChange={setActiveTab}
            moveButton={
              <MoveNextStageButton
                applicationId={data.applicationId}
                canMoveForward={permissions.canMove && data.actions.canMoveForward}
              />
            }
          />

          {activeTab === "Тест" && (
            testLoading ? (
              <p style={{ color: "#626262", fontSize: 14 }}>Загрузка теста...</p>
            ) : testData ? (
              <TestInfoSection data={testData} />
            ) : (
              <p style={{ color: "#626262", fontSize: 14 }}>Данные теста недоступны.</p>
            )
          )}
        </div>
      </div>
    </main>
  );
}
