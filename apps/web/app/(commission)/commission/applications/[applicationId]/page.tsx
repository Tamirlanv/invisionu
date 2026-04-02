"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { CommissionCommentBlock } from "@/components/commission/detail/CommissionCommentBlock";
import { MoveNextStageButton } from "@/components/commission/detail/MoveNextStageButton";
import { PersonalInfoSection } from "@/components/commission/detail/PersonalInfoSection";
import { ReviewScoreBlock } from "@/components/commission/detail/ReviewScoreBlock";
import { TestInfoSection } from "@/components/commission/detail/TestInfoSection";
import { ApiError } from "@/lib/api-client";
import { permissionsFromRole } from "@/lib/commission/permissions";
import {
  deleteCommissionApplication,
  getCommissionApplicationPersonalInfo,
  getCommissionApplicationTestInfo,
  getCommissionRole,
  getCommissionSidebarPanel,
  getSectionReviewScores,
  saveSectionReviewScores,
} from "@/lib/commission/query";
import type {
  CommissionApplicationPersonalInfoView,
  CommissionSidebarPanelView,
  CommissionApplicationTestInfoView,
  CommissionRole,
  ReviewScoreBlock as ReviewScoreBlockType,
} from "@/lib/commission/types";
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

  const stage = data.stageContext?.currentStage;
  if (stage && stage !== "initial_screening" && stage !== "data_check") {
    if (ps.overall === "partial") return null;
  }

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

  const [sidebarPanel, setSidebarPanel] = useState<CommissionSidebarPanelView | null>(null);
  const [sidebarLoading, setSidebarLoading] = useState(false);
  const lastSidebarTabRef = useRef<string>("");

  const [sectionScores, setSectionScores] = useState<ReviewScoreBlockType | null>(null);
  const [scoresLoading, setScoresLoading] = useState(false);
  const lastScoresTabRef = useRef<string>("");

  async function handleDelete() {
    if (!applicationId || deleteRef.current) return;
    if (!confirm("Удалить заявку? Это действие необратимо.")) return;
    deleteRef.current = true;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteCommissionApplication(applicationId!);
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
          getCommissionApplicationPersonalInfo(applicationId!),
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
    if (!applicationId || lastSidebarTabRef.current === activeTab) return;
    lastSidebarTabRef.current = activeTab;
    let cancelled = false;
    setSidebarLoading(true);
    getCommissionSidebarPanel(applicationId!, activeTab)
      .then((panel) => {
        if (!cancelled) setSidebarPanel(panel);
      })
      .catch(() => {
        if (!cancelled) setSidebarPanel(null);
      })
      .finally(() => {
        if (!cancelled) setSidebarLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeTab, applicationId]);

  useEffect(() => {
    if (activeTab !== "Тест" || !applicationId || testFetchedRef.current) return;
    let cancelled = false;
    testFetchedRef.current = true;
    setTestLoading(true);
    getCommissionApplicationTestInfo(applicationId!)
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

  useEffect(() => {
    if (!applicationId || activeTab === "Личная информация" || lastScoresTabRef.current === activeTab) return;
    lastScoresTabRef.current = activeTab;
    let cancelled = false;
    setScoresLoading(true);
    getSectionReviewScores(applicationId!, activeTab)
      .then((result) => {
        if (!cancelled) setSectionScores(result);
      })
      .catch(() => {
        if (!cancelled) setSectionScores(null);
      })
      .finally(() => {
        if (!cancelled) setScoresLoading(false);
      });
    return () => { cancelled = true; };
  }, [activeTab, applicationId]);

  const permissions = useMemo(() => permissionsFromRole(role), [role]);

  const _TAB_TO_SECTION: Record<string, string> = useMemo(() => ({
    "Личная информация": "personal",
    "Тест": "test",
    "Мотивация": "motivation",
    "Путь": "path",
    "Достижения": "achievements",
  }), []);

  const handleSaveScores = useCallback(
    async (scores: Array<{ key: string; score: number }>) => {
      if (!applicationId) return;
      const section = _TAB_TO_SECTION[activeTab] ?? "personal";
      const updated = await saveSectionReviewScores(applicationId!, section, scores);
      setSectionScores(updated);
    },
    [applicationId, activeTab, _TAB_TO_SECTION],
  );

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

  return (
    <main className={styles.root}>
      <div className={styles.header}>
        <h1 className={styles.pageTitle}>Страница ученика</h1>
        <Link href="/commission" style={{ fontSize: 14, color: "#626262", textDecoration: "none" }}>
          ← К доске
        </Link>
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

          {/* Card 2: Sidebar panel — swaps based on active tab */}
          <section className={styles.sideCard}>
            <h3 className={styles.aiTitle}>{sidebarPanel?.title ?? "Summary"}</h3>
            {sidebarLoading ? (
              <p className={styles.aiText}>Загрузка...</p>
            ) : sidebarPanel ? (
              <div style={{ display: "grid", gap: 16 }}>
                {sidebarPanel.sections.map((section) => (
                  <div key={section.title} style={{ display: "grid", gap: 4 }}>
                    <p className={styles.aiLabel}>{section.title}</p>
                    {section.items.map((item, i) => (
                      <p key={i} className={styles.aiText}>
                        {item}
                      </p>
                    ))}
                  </div>
                ))}
              </div>
            ) : (
              <p className={styles.aiText}>Данные недоступны.</p>
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

          {activeTab === "Мотивация" && (
            <section style={{ display: "grid", gap: 12 }}>
              <h3
                style={{
                  margin: 0,
                  fontSize: 32,
                  fontWeight: 550,
                  color: "#262626",
                  letterSpacing: "-0.96px",
                  lineHeight: "32px",
                }}
              >
                Мотивационное письмо
              </h3>
              <p
                style={{
                  margin: 0,
                  fontSize: 14,
                  fontWeight: 350,
                  color: "#626262",
                  letterSpacing: "-0.42px",
                  lineHeight: "14px",
                }}
              >
                Ответ абитуриента
              </p>
              <p
                style={{
                  margin: 0,
                  fontSize: 16,
                  fontWeight: 350,
                  color: "#262626",
                  letterSpacing: "-0.48px",
                  lineHeight: "22px",
                  whiteSpace: "pre-wrap",
                }}
              >
                {data.motivation?.narrative ?? "Мотивационное письмо не заполнено."}
              </p>
            </section>
          )}

          {activeTab === "Путь" && (
            <section style={{ display: "grid", gap: 40 }}>
              {data.path && data.path.length > 0 ? (
                data.path.map((item, idx) => (
                  <div key={idx} style={{ display: "grid", gap: 8 }}>
                    <h3
                      style={{
                        margin: 0,
                        fontSize: 32,
                        fontWeight: 550,
                        color: "#262626",
                        letterSpacing: "-0.96px",
                        lineHeight: "32px",
                      }}
                    >
                      {item.questionTitle}
                    </h3>
                    <p
                      style={{
                        margin: "4px 0 0",
                        fontSize: 14,
                        fontWeight: 350,
                        color: "#626262",
                        letterSpacing: "-0.42px",
                        lineHeight: "14px",
                      }}
                    >
                      Ответ абитуриента
                    </p>
                    <p
                      style={{
                        margin: "2px 0 0",
                        fontSize: 16,
                        fontWeight: 350,
                        color: "#626262",
                        letterSpacing: "-0.48px",
                        lineHeight: "22px",
                      }}
                    >
                      {item.description}
                    </p>
                    <p
                      style={{
                        margin: "8px 0 0",
                        fontSize: 16,
                        fontWeight: 400,
                        color: "#262626",
                        letterSpacing: "-0.48px",
                        lineHeight: "24px",
                        whiteSpace: "pre-wrap",
                      }}
                    >
                      {item.text}
                    </p>
                  </div>
                ))
              ) : (
                <p style={{ margin: 0, fontSize: 14, color: "#626262" }}>
                  Раздел «Путь» не заполнен.
                </p>
              )}
            </section>
          )}

          {activeTab === "Достижения" && (
            <section style={{ display: "grid", gap: 32 }}>
              <div style={{ display: "grid", gap: 12 }}>
                <h3
                  style={{
                    margin: 0,
                    fontSize: 32,
                    fontWeight: 550,
                    color: "#262626",
                    letterSpacing: "-0.96px",
                    lineHeight: "32px",
                  }}
                >
                  Описание
                </h3>
                <p
                  style={{
                    margin: 0,
                    fontSize: 14,
                    fontWeight: 350,
                    color: "#626262",
                    letterSpacing: "-0.42px",
                    lineHeight: "14px",
                  }}
                >
                  Ответ абитуриента
                </p>
                <p
                  style={{
                    margin: 0,
                    fontSize: 16,
                    fontWeight: 350,
                    color: "#262626",
                    letterSpacing: "-0.48px",
                    lineHeight: "24px",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {data.achievements?.text ?? "Раздел «Достижения» не заполнен."}
                </p>
              </div>

              <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(2, minmax(200px, 1fr))" }}>
                <div style={{ display: "grid", gap: 6 }}>
                  <p
                    style={{
                      margin: 0,
                      fontSize: 14,
                      fontWeight: 350,
                      color: "#626262",
                      letterSpacing: "-0.42px",
                      lineHeight: "14px",
                    }}
                  >
                    Роль
                  </p>
                  <p
                    style={{
                      margin: 0,
                      fontSize: 16,
                      fontWeight: 350,
                      color: "#262626",
                      letterSpacing: "-0.48px",
                      lineHeight: "16px",
                    }}
                  >
                    {data.achievements?.role ?? "—"}
                  </p>
                </div>

                <div style={{ display: "grid", gap: 6 }}>
                  <p
                    style={{
                      margin: 0,
                      fontSize: 14,
                      fontWeight: 350,
                      color: "#626262",
                      letterSpacing: "-0.42px",
                      lineHeight: "14px",
                    }}
                  >
                    Год
                  </p>
                  <p
                    style={{
                      margin: 0,
                      fontSize: 16,
                      fontWeight: 350,
                      color: "#262626",
                      letterSpacing: "-0.48px",
                      lineHeight: "16px",
                    }}
                  >
                    {data.achievements?.year ?? "—"}
                  </p>
                </div>
              </div>

              <div style={{ display: "grid", gap: 12 }}>
                <h3
                  style={{
                    margin: 0,
                    fontSize: 32,
                    fontWeight: 550,
                    color: "#262626",
                    letterSpacing: "-0.96px",
                    lineHeight: "32px",
                  }}
                >
                  Источники
                </h3>
                {data.achievements?.links?.length ? (
                  <div style={{ display: "grid", gap: 14 }}>
                    {data.achievements.links.map((ln, idx) => (
                      <div key={`${ln.url}-${idx}`} style={{ display: "grid", gap: 4 }}>
                        <p
                          style={{
                            margin: 0,
                            fontSize: 16,
                            fontWeight: 350,
                            color: "#262626",
                            letterSpacing: "-0.48px",
                            lineHeight: "16px",
                          }}
                        >
                          {ln.label}
                        </p>
                        <a
                          href={ln.url}
                          target="_blank"
                          rel="noreferrer"
                          style={{
                            margin: 0,
                            fontSize: 16,
                            fontWeight: 350,
                            color: "#4facea",
                            letterSpacing: "-0.48px",
                            lineHeight: "16px",
                            textDecoration: "none",
                            wordBreak: "break-word",
                          }}
                        >
                          {ln.url}
                        </a>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p style={{ margin: 0, fontSize: 14, color: "#626262" }}>Ссылки не добавлены.</p>
                )}
              </div>
            </section>
          )}

          {activeTab !== "Личная информация" && (
            scoresLoading ? (
              <p style={{ color: "#626262", fontSize: 14, marginTop: 16 }}>Загрузка оценок...</p>
            ) : sectionScores && sectionScores.items.length > 0 ? (
              <div style={{ marginTop: 24 }}>
                <ReviewScoreBlock
                  data={sectionScores}
                  onSave={handleSaveScores}
                  canEdit={permissions.canComment}
                />
              </div>
            ) : null
          )}

          {permissions.canMove ? (
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 32 }}>
              <button
                type="button"
                onClick={() => void handleDelete()}
                disabled={deleting}
                style={{
                  fontSize: 14,
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
              {deleteError ? (
                <span style={{ fontSize: 13, color: "#e53935" }}>{deleteError}</span>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </main>
  );
}
