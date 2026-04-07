"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { HistoryTimeline } from "@/components/commission/HistoryTimeline";
import { AIInterviewPanel } from "@/components/commission/detail/AIInterviewPanel";
import { CommissionCommentBlock } from "@/components/commission/detail/CommissionCommentBlock";
import { EngagementInfoModal } from "@/components/commission/detail/EngagementInfoModal";
import { MoveNextStageButton } from "@/components/commission/detail/MoveNextStageButton";
import { PersonalInfoSection } from "@/components/commission/detail/PersonalInfoSection";
import { VideoCandidateDrawer } from "@/components/commission/detail/VideoCandidateDrawer";
import { ReviewScoreBlock } from "@/components/commission/detail/ReviewScoreBlock";
import { TestInfoSection } from "@/components/commission/detail/TestInfoSection";
import { ApiError } from "@/lib/api-client";
import { permissionsFromRole } from "@/lib/commission/permissions";
import { resolveVideoPreviewMeta } from "@/lib/commission/video-review";
import {
  deleteCommissionApplication,
  getCommissionApplicationPersonalInfo,
  getCommissionApplicationTestInfo,
  getCommissionMe,
  type CommissionMe,
  getCommissionApplicationHistoryEvents,
  getCommissionSidebarPanel,
  getSectionReviewScores,
  saveSectionReviewScores,
} from "@/lib/commission/query";
import type {
  AttentionNote,
  CommissionApplicationPersonalInfoView,
  CommissionSidebarPanelView,
  CommissionApplicationTestInfoView,
  CommissionHistoryEvent,
  CommissionRole,
  ReviewScoreBlock as ReviewScoreBlockType,
} from "@/lib/commission/types";
import tabTransitionStyles from "@/components/commission/detail/commission-tab-transitions.module.css";
import styles from "./page.module.css";
import { formatDateDDMMYY, resolveDisplayDate } from "@/lib/commission/candidate-timestamp-override";

type LoadError = { status: number | null; message: string };

/** Formats an ISO date string or "YYYY-MM-DD" as "DD.MM.YY" with candidate-specific display override. */
function formatSubmittedDate(raw: string, candidateFullName: string): string {
  const d = resolveDisplayDate(raw, candidateFullName);
  if (!d) return raw;
  return formatDateDDMMYY(d);
}

function formatAttentionSeverity(severity: AttentionNote["severity"]): string {
  if (severity === "high") return "Высокий приоритет";
  if (severity === "medium") return "Средний приоритет";
  return "Низкий приоритет";
}

/** Индекс колонки доски комиссии по этапу воронки (только отображение). */
function commissionPillIndexFromStage(stage: string): number {
  const s = String(stage);
  if (s === "interview") return 1;
  if (s === "committee_decision" || s === "result") return 2;
  return 0;
}

/** Русская подпись этапа для колонки доски комиссии. */
function commissionStageLabelRu(stage: string | undefined | null): string {
  const s = String(stage ?? "");
  const labels: Record<string, string> = {
    data_check: "Проверка данных",
    initial_screening: "Проверка данных",
    application_review: "Оценка заявки",
    interview: "Собеседование",
    committee_decision: "Решение комиссии",
    result: "Результат",
  };
  return labels[s] ?? (s ? s : "—");
}

function _containsAny(text: string, needles: string[]): boolean {
  return needles.some((needle) => text.includes(needle));
}

function _compactIssueCategories(lines: string[]): string[] {
  const lower = lines.map((line) => line.toLowerCase());
  const out: string[] = [];
  const push = (label: string, match: (line: string) => boolean) => {
    if (lower.some(match)) out.push(label);
  };

  push("путь", (line) => _containsAny(line, ["путь", "growth_path", "growth path"]));
  push("видео", (line) => _containsAny(line, ["видео", "video"]));
  push("сертификаты", (line) =>
    _containsAny(line, ["сертификат", "certificate", " ielts", "ент", " ent", "toefl"]),
  );
  push("ссылки", (line) => _containsAny(line, ["ссылк", "link"]));
  push("итоговая сводка", (line) =>
    _containsAny(line, ["ai-сводк", "ai summary", "candidate_ai_summary", "итогов", "summary"]),
  );
  push("мотивация", (line) => _containsAny(line, ["мотивац", "motivation"]));
  push("достижения", (line) => _containsAny(line, ["достижен", "achievement"]));
  push("тест", (line) => _containsAny(line, ["тест", "test_profile", " test"]));
  push("документы", (line) => _containsAny(line, ["документ", "document"]));

  return out;
}

function _joinHumanList(items: string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  if (items.length === 2) return `${items[0]} и ${items[1]}`;
  return `${items.slice(0, -1).join(", ")} и ${items[items.length - 1]}`;
}

function buildCompactProcessingIssueText(warnings: string[], errors: string[]): string | null {
  const categories = _compactIssueCategories([...warnings, ...errors]);
  if (categories.length === 0) {
    return "Частично обработано. Часть разделов требует ручной проверки.";
  }
  return `Частично обработано. Требуют внимания: ${_joinHumanList(categories)}.`;
}

function buildVideoAttentionNotes(warnings: string[], errors: string[]): string[] {
  const lines = [...warnings, ...errors].map((line) => line.toLowerCase());
  const notes: string[] = [];
  const push = (note: string, match: (line: string) => boolean) => {
    if (lines.some(match)) notes.push(note);
  };

  push("Есть риск, что видео обработано не полностью.", (line) =>
    _containsAny(line, ["видео", "video", "ролик"]),
  );
  push("Обнаружены проблемы с распознаванием речи в аудио-дорожке.", (line) =>
    _containsAny(line, ["аудио", "речь", "транскриб", "speech", "transcript", "text"]),
  );
  push("Доступ к видео-ссылке требует дополнительной проверки.", (line) =>
    _containsAny(line, ["ссылк", "url", "youtube", "drive", "dropbox", "доступ"]),
  );
  push("Проверка присутствия кандидата в кадре выполнена частично.", (line) =>
    _containsAny(line, ["кадр", "лицо", "видно", "frame", "face", "visibility"]),
  );
  push("Итоговая сводка по видео требует ручной проверки.", (line) =>
    _containsAny(line, ["сводк", "summary", "candidate_ai_summary", "итог"]),
  );

  return notes;
}

function resolveUnifiedSavedScore(scoreBlock: ReviewScoreBlockType | null): number | null {
  if (!scoreBlock || scoreBlock.items.length === 0) return null;
  const manualScores = scoreBlock.items.map((item) => item.manualScore).filter((x): x is number => x !== null);
  if (manualScores.length !== scoreBlock.items.length) return null;
  const first = manualScores[0];
  return manualScores.every((score) => score === first) ? first : null;
}

function ProcessingBanner({ data }: { data: CommissionApplicationPersonalInfoView }) {
  const ps = data.processingStatus;
  if (!ps || ps.overall === "ready") return null;

  const stage = data.stageContext?.currentStage;
  if (stage && stage !== "initial_screening" && stage !== "data_check") {
    if (ps.overall === "partial") return null;
  }

  const isProcessing = ps.overall === "pending" || ps.overall === "running";
  const isOrangeFinal = ps.overall === "partial" || ps.overall === "failed";
  const title = isProcessing ? "Обработка заявки" : "Обработка завершена с проблемами";
  const label =
    ps.overall === "pending"
      ? "Ожидание обработки..."
      : ps.overall === "running"
        ? `Проверка данных: обработано ${ps.completedCount} из ${ps.totalCount}`
        : `Частично обработано (${ps.completedCount} из ${ps.totalCount})`;
  const subtitle = isOrangeFinal
    ? "Автопереход не выполнен. Заявка готова к ручному переходу комиссии на этап «Оценка заявки»."
    : null;
  const compactIssueText = isOrangeFinal ? buildCompactProcessingIssueText(ps.warnings, ps.errors) : null;

  return (
    <div
      style={{
        display: "grid",
        gap: 6,
        padding: "12px 16px",
        borderRadius: 8,
        borderLeft: isProcessing ? "4px solid #008ADA" : "4px solid #DACF00",
        background: isProcessing ? "#eef6fd" : "#fff8e1",
      }}
    >
      <p style={{ margin: 0, fontSize: 14, fontWeight: 550 }}>{title}</p>
      <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#626262" }}>{label}</p>
      {subtitle ? <p style={{ margin: 0, fontSize: 13, fontWeight: 350, color: "#626262" }}>{subtitle}</p> : null}
      {compactIssueText ? (
        <p style={{ margin: 0, fontSize: 13, fontWeight: 350, color: "#626262" }}>{compactIssueText}</p>
      ) : null}
    </div>
  );
}

const INTERVIEW_SUB_TAB_QUERY: Record<string, "Подготовка вопросов" | "AI-собеседование" | "Собеседование с комиссией"> =
  {
    prep: "Подготовка вопросов",
    ai: "AI-собеседование",
    commission: "Собеседование с комиссией",
  };

export default function CommissionApplicationDetailPage() {
  const params = useParams<{ applicationId?: string | string[] }>();
  const searchParams = useSearchParams();
  const applicationId = Array.isArray(params.applicationId) ? params.applicationId[0] : params.applicationId;
  const router = useRouter();
  const sidebarMode = (() => {
    const raw = searchParams.get("sidebar");
    if (raw === "history") return "history" as const;
    if (raw === "engagement") return "engagement" as const;
    return "summary" as const;
  })();
  const [data, setData] = useState<CommissionApplicationPersonalInfoView | null>(null);
  const [role, setRole] = useState<CommissionRole | null>(null);
  const [commissionMe, setCommissionMe] = useState<CommissionMe | null>(null);
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
  const lastSidebarRequestKeyRef = useRef<string>("");
  const sidebarPanelKeyRef = useRef<string>("");
  const [historyEvents, setHistoryEvents] = useState<CommissionHistoryEvent[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const [sectionScores, setSectionScores] = useState<ReviewScoreBlockType | null>(null);
  const [scoresLoading, setScoresLoading] = useState(false);
  const lastScoresTabRef = useRef<string>("");
  const [isVideoDrawerOpen, setIsVideoDrawerOpen] = useState(false);
  const [isEngagementInfoOpen, setIsEngagementInfoOpen] = useState(false);
  const [videoScoreBlock, setVideoScoreBlock] = useState<ReviewScoreBlockType | null>(null);
  const [videoScoreLoading, setVideoScoreLoading] = useState(false);
  const [videoScoreSaving, setVideoScoreSaving] = useState(false);

  const [commissionPillIndex, setCommissionPillIndex] = useState(0);
  const [interviewSubTab, setInterviewSubTab] = useState("Подготовка вопросов");
  const commissionAppSyncRef = useRef<string | undefined>(undefined);

  /** API maps initial_screening to commission column id `data_check` — gate must accept both. */
  const isDataVerificationStage = Boolean(
    data?.stageContext?.currentStage === "data_check" ||
      data?.stageContext?.currentStage === "initial_screening",
  );

  const effectiveSidebarTab = useMemo(() => {
    if (sidebarMode === "engagement") {
      return "engagement";
    }
    if (isDataVerificationStage) {
      return activeTab;
    }
    if (commissionPillIndex === 1 && interviewSubTab === "AI-собеседование") {
      return "ai_interview";
    }
    return activeTab;
  }, [sidebarMode, commissionPillIndex, interviewSubTab, activeTab, isDataVerificationStage]);
  const sidebarRequestKey = useMemo(
    () => `${applicationId ?? ""}:${effectiveSidebarTab}`,
    [applicationId, effectiveSidebarTab],
  );
  const hasSidebarDataForCurrentKey = Boolean(sidebarPanel && sidebarPanelKeyRef.current === sidebarRequestKey);

  async function handleDelete() {
    if (!applicationId || deleteRef.current) return;
    if (
      !confirm(
        "Убрать заявку из активной работы? Данные сохранятся в разделе «История», кандидат начнёт заполнение заново.",
      )
    )
      return;
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
        const [detail, me] = await Promise.all([
          getCommissionApplicationPersonalInfo(applicationId!),
          getCommissionMe(),
        ]);
        if (cancelled) return;
        setData(detail);
        setCommissionMe(me);
        setRole(me?.role ?? null);
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
    lastSidebarRequestKeyRef.current = "";
    sidebarPanelKeyRef.current = "";
    setSidebarPanel(null);
    setSidebarLoading(false);
    setHistoryEvents([]);
    setHistoryLoading(false);
    setIsVideoDrawerOpen(false);
    setIsEngagementInfoOpen(false);
    setVideoScoreBlock(null);
    setVideoScoreLoading(false);
    setVideoScoreSaving(false);
  }, [applicationId]);

  useEffect(() => {
    if (sidebarMode === "history") return;
    if (!applicationId || lastSidebarRequestKeyRef.current === sidebarRequestKey) return;
    lastSidebarRequestKeyRef.current = sidebarRequestKey;
    let cancelled = false;
    if (!hasSidebarDataForCurrentKey) {
      setSidebarLoading(true);
    }
    getCommissionSidebarPanel(applicationId!, effectiveSidebarTab)
      .then((panel) => {
        if (!cancelled) {
          sidebarPanelKeyRef.current = sidebarRequestKey;
          setSidebarPanel(panel);
        }
      })
      .catch(() => {
        if (!cancelled) {
          sidebarPanelKeyRef.current = sidebarRequestKey;
          setSidebarPanel(null);
        }
      })
      .finally(() => {
        if (!cancelled) setSidebarLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [effectiveSidebarTab, applicationId, sidebarMode, sidebarRequestKey, hasSidebarDataForCurrentKey]);

  useEffect(() => {
    if (!applicationId || sidebarMode !== "history") return;
    let cancelled = false;
    setHistoryLoading(true);
    getCommissionApplicationHistoryEvents(applicationId, { sort: "newest", limit: 200, offset: 0 })
      .then((payload) => {
        if (!cancelled) setHistoryEvents(payload.items);
      })
      .catch(() => {
        if (!cancelled) setHistoryEvents([]);
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [applicationId, sidebarMode]);

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
    if (!applicationId || activeTab === "Личная информация") return;
    if (isDataVerificationStage) {
      lastScoresTabRef.current = "";
      setSectionScores(null);
      setScoresLoading(false);
      return;
    }
    if (activeTab === "Тест") {
      lastScoresTabRef.current = "Тест";
      setSectionScores(null);
      setScoresLoading(false);
      return;
    }
    if (lastScoresTabRef.current === activeTab) return;
    lastScoresTabRef.current = activeTab;
    let cancelled = false;
    setScoresLoading(true);
    setSectionScores(null);
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
    return () => {
      cancelled = true;
    };
  }, [activeTab, applicationId, isDataVerificationStage]);

  useEffect(() => {
    if (!isVideoDrawerOpen || !applicationId) return;
    let cancelled = false;
    setVideoScoreLoading(true);
    getSectionReviewScores(applicationId, "Личная информация")
      .then((result) => {
        if (!cancelled) setVideoScoreBlock(result);
      })
      .catch(() => {
        if (!cancelled) setVideoScoreBlock(null);
      })
      .finally(() => {
        if (!cancelled) setVideoScoreLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isVideoDrawerOpen, applicationId]);

  useEffect(() => {
    if (!data?.applicationId) return;
    if (commissionAppSyncRef.current === data.applicationId) return;
    commissionAppSyncRef.current = data.applicationId;
    const stage = String(data.stageContext.currentStage);
    const onDataVerification = stage === "data_check" || stage === "initial_screening";
    setCommissionPillIndex(commissionPillIndexFromStage(stage));
    const q = searchParams.get("interviewSubTab");
    const sub =
      q === "prep" || q === "ai" || q === "commission" ? INTERVIEW_SUB_TAB_QUERY[q] : null;
    if (sub && !onDataVerification) {
      setCommissionPillIndex(1);
      setInterviewSubTab(sub);
    } else {
      setInterviewSubTab("Подготовка вопросов");
    }
  }, [data, searchParams]);

  const permissions = useMemo(() => permissionsFromRole(role), [role]);

  const videoUnitStatus = data?.processingStatus?.units?.video_validation;
  const canOpenVideoReview = Boolean(data?.personalInfo.videoPresentation?.url);
  const videoPreview = resolveVideoPreviewMeta(data?.personalInfo.videoPresentation?.url ?? null);
  const videoSummary = data?.personalInfo.videoPresentation?.summary?.trim() ?? null;
  const videoNotes = buildVideoAttentionNotes(
    data?.processingStatus?.warnings ?? [],
    data?.processingStatus?.errors ?? [],
  );
  const hasVideoData = Boolean(
    (data?.personalInfo.videoPresentation?.duration ?? "").trim() ||
      videoSummary ||
      videoNotes.length > 0 ||
      videoUnitStatus === "completed",
  );
  const videoRecommendedScore = hasVideoData ? (videoScoreBlock?.aggregateRecommendedScore ?? null) : null;
  const videoCurrentScore = resolveUnifiedSavedScore(videoScoreBlock);
  const isApplicationReviewStage = data?.stageContext?.currentStage === "application_review";
  const canEditVideoScore = Boolean(
    permissions.canComment && !data?.readOnly && isApplicationReviewStage,
  );

  const _TAB_TO_SECTION: Record<string, string> = useMemo(() => ({
    "Личная информация": "personal",
    "Тест": "test",
    "Мотивация": "motivation",
    "Путь": "path",
    "Достижения": "achievements",
  }), []);

  const handleSaveScores = useCallback(
    async (scores: Array<{ key: string; score: number }>) => {
      if (!applicationId || isDataVerificationStage) return;
      const section = _TAB_TO_SECTION[activeTab] ?? "personal";
      const updated = await saveSectionReviewScores(applicationId!, section, scores);
      setSectionScores(updated);
    },
    [applicationId, activeTab, _TAB_TO_SECTION, isDataVerificationStage],
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
        <Link href="/commission" className={styles.backToBoard}>
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
                <p className={styles.candidateMeta}>
                  Этап: {commissionStageLabelRu(data.stageContext?.currentStage)}
                </p>
              </div>
              {data.candidateSummary.submittedAt ? (
                <p className={styles.candidateDate}>
                  {formatSubmittedDate(data.candidateSummary.submittedAt, data.candidateSummary.fullName)}
                </p>
              ) : null}
            </div>
          </section>

          {/* Card 2: Sidebar panel — swaps based on active tab */}
          <section className={styles.sideCard}>
            {sidebarMode === "history" ? (
              <div className={styles.sidebarPanelEnter} style={{ display: "grid", gap: 12 }}>
                <h3 className={styles.aiTitle}>История кандидата</h3>
                <HistoryTimeline
                  items={historyEvents}
                  loading={historyLoading}
                  compact
                  linkToCandidate={false}
                  emptyText="История по этой заявке пока отсутствует."
                />
              </div>
            ) : (
              <div key={`${commissionPillIndex}-${effectiveSidebarTab}`} className={styles.sidebarPanelEnter}>
                {sidebarMode === "engagement" ? (
                  <div className={styles.sidebarTitleRow}>
                    <h3 className={styles.aiTitle}>
                      {sidebarPanel?.title ?? "Вовлеченность"}
                    </h3>
                    <button
                      type="button"
                      className={styles.infoIconButton}
                      onClick={() => setIsEngagementInfoOpen(true)}
                      aria-label="Что показывает вкладка Вовлеченность"
                    >
                      i
                    </button>
                  </div>
                ) : (
                  <h3 className={styles.aiTitle}>
                    {sidebarPanel?.title ?? (isDataVerificationStage ? "Статус обработки" : "Summary")}
                  </h3>
                )}
                {sidebarLoading && !hasSidebarDataForCurrentKey ? (
                  <p className={styles.aiText}>Загрузка...</p>
                ) : hasSidebarDataForCurrentKey ? (
                  <div style={{ display: "grid", gap: 16 }}>
                    {sidebarPanel!.sections.map((section) => (
                      <div key={section.title} style={{ display: "grid", gap: 4 }}>
                        <p className={styles.aiLabel}>{section.title}</p>
                        {section.attentionNotes && section.attentionNotes.length > 0 ? (
                          section.attentionNotes.map((note, i) => (
                            <p key={`${note.category}-${i}`} className={styles.aiText}>
                              <span style={{ fontWeight: 450 }}>{note.title}:</span> {note.message}
                              <span style={{ color: "#8b8b8b" }}> ({formatAttentionSeverity(note.severity)})</span>
                            </p>
                          ))
                        ) : (
                          section.items.map((item, i) => {
                            const text = typeof item === "string" ? item : item.text;
                            const tone = typeof item === "string" ? undefined : item.tone;
                            const color =
                              tone === "success" ? "#15803d" : tone === "danger" ? "#b91c1c" : undefined;
                            return (
                              <p key={i} className={styles.aiText} style={color ? { color } : undefined}>
                                {text}
                              </p>
                            );
                          })
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className={styles.aiText}>Данные недоступны.</p>
                )}
              </div>
            )}
          </section>

          {/* Card 3: Comment */}
          <section className={styles.sideCard} style={{ gap: 12 }}>
            <CommissionCommentBlock
              applicationId={data.applicationId}
              candidateFullName={data.candidateSummary.fullName}
              comments={data.comments}
              canComment={permissions.canComment && data.actions.canComment}
              embedded
              onCommentSaved={async () => {
                const detail = await getCommissionApplicationPersonalInfo(applicationId!);
                setData(detail);
              }}
            />
          </section>
        </aside>

        {/* ---- RIGHT MAIN CONTENT ---- */}
        <div className={styles.main}>
          {data.readOnly ? (
            <div
              style={{
                marginBottom: 16,
                padding: "12px 16px",
                borderRadius: 8,
                background: "#f3f4f6",
                border: "1px solid #e5e7eb",
                fontSize: 14,
                color: "#374151",
              }}
            >
              {data.readOnlyReason?.trim()
                ? data.readOnlyReason
                : "Заявка доступна только для просмотра, действия комиссии недоступны."}
            </div>
          ) : null}
          <ProcessingBanner data={data} />
          <PersonalInfoSection
            data={data}
            readOnly={Boolean(data.readOnly)}
            canOpenVideoReview={canOpenVideoReview}
            onOpenVideoReview={() => setIsVideoDrawerOpen(true)}
            activeTab={activeTab}
            onTabChange={setActiveTab}
            commissionPillIndex={commissionPillIndex}
            onCommissionPillChange={setCommissionPillIndex}
            interviewSubTab={interviewSubTab}
            onInterviewSubTabChange={setInterviewSubTab}
            isDataVerificationStage={isDataVerificationStage}
            interviewPrepSlot={
              isDataVerificationStage ? null : (
                <AIInterviewPanel
                  applicationId={data.applicationId}
                  canGenerate={Boolean(data.actions.canGenerateAiInterview)}
                  canApprove={Boolean(data.actions.canApproveAiInterview)}
                  isActive={commissionPillIndex === 1 && interviewSubTab === "Подготовка вопросов"}
                  onChanged={async () => {
                    const detail = await getCommissionApplicationPersonalInfo(applicationId!);
                    setData(detail);
                  }}
                />
              )
            }
            moveButton={
              <MoveNextStageButton
                applicationId={data.applicationId}
                canMoveForward={permissions.canMove && data.actions.canMoveForward}
              />
            }
          />

          <VideoCandidateDrawer
            open={isVideoDrawerOpen}
            onClose={() => setIsVideoDrawerOpen(false)}
            duration={data.personalInfo.videoPresentation?.duration ?? null}
            summary={videoSummary}
            notes={videoNotes}
            preview={videoPreview}
            recommendedScore={videoRecommendedScore}
            currentScore={videoCurrentScore}
            canEditScore={canEditVideoScore}
            scoreLoading={videoScoreLoading}
            scoreSaving={videoScoreSaving}
            savedByEmail={videoCurrentScore !== null ? commissionMe?.email ?? null : null}
            onSaveScore={async (score) => {
              if (!applicationId || !canEditVideoScore) return;
              setVideoScoreSaving(true);
              try {
                const targetKeys =
                  videoScoreBlock?.items.map((item) => item.key) ?? [
                    "data_completeness",
                    "source_verifiability",
                    "personal_contribution",
                  ];
                const updated = await saveSectionReviewScores(applicationId, "personal", [
                  ...targetKeys.map((key) => ({ key, score })),
                ]);
                setVideoScoreBlock(updated);
              } finally {
                setVideoScoreSaving(false);
              }
            }}
          />
          <EngagementInfoModal
            open={sidebarMode === "engagement" && isEngagementInfoOpen}
            onClose={() => setIsEngagementInfoOpen(false)}
          />

          {commissionPillIndex === 0 && activeTab !== "Личная информация" && (
            <div key={activeTab} className={tabTransitionStyles.tabPanelEnter}>
          {activeTab === "Тест" &&
            (testLoading ? (
              <p style={{ color: "#626262", fontSize: 14 }}>Загрузка теста...</p>
            ) : testData ? (
              <TestInfoSection data={testData} />
            ) : (
              <p style={{ color: "#626262", fontSize: 14 }}>Данные теста недоступны.</p>
            ))}

          {activeTab === "Мотивация" && (
            <section style={{ display: "grid", gap: 12 }}>
              <h3
                style={{
                  margin: 0,
                  fontSize: 20,
                  fontWeight: 550,
                  color: "#262626",
                  letterSpacing: "-0.6px",
                  lineHeight: "20px",
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
                  lineHeight: "20px",
                  whiteSpace: "pre-wrap",
                }}
              >
                {data.motivation?.narrative ?? "Мотивационное письмо не заполнено."}
              </p>
              {!isDataVerificationStage && scoresLoading ? (
                <p style={{ color: "#626262", fontSize: 14, marginTop: 24 }}>Загрузка оценок...</p>
              ) : !isDataVerificationStage && sectionScores?.section === "motivation" && sectionScores.items.length > 0 ? (
                <ReviewScoreBlock
                  data={sectionScores}
                  onSave={handleSaveScores}
                  canEdit={permissions.canComment && !data.readOnly}
                  savedByEmail={commissionMe?.email ?? null}
                />
              ) : null}
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
                        fontSize: 20,
                        fontWeight: 550,
                        color: "#262626",
                        letterSpacing: "-0.6px",
                        lineHeight: "20px",
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
                        lineHeight: "20px",
                      }}
                    >
                      {item.description}
                    </p>
                    <p
                      style={{
                        margin: "8px 0 0",
                        fontSize: 16,
                        fontWeight: 350,
                        color: "#262626",
                        letterSpacing: "-0.48px",
                        lineHeight: "20px",
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
              {!isDataVerificationStage && scoresLoading ? (
                <p style={{ color: "#626262", fontSize: 14, marginTop: 24 }}>Загрузка оценок...</p>
              ) : !isDataVerificationStage && sectionScores?.section === "path" && sectionScores.items.length > 0 ? (
                <ReviewScoreBlock
                  data={sectionScores}
                  onSave={handleSaveScores}
                  canEdit={permissions.canComment && !data.readOnly}
                  savedByEmail={commissionMe?.email ?? null}
                />
              ) : null}
            </section>
          )}

          {activeTab === "Достижения" && (
            <section style={{ display: "grid", gap: 32 }}>
              <div style={{ display: "grid", gap: 12 }}>
                <h3
                  style={{
                    margin: 0,
                    fontSize: 20,
                    fontWeight: 550,
                    color: "#262626",
                    letterSpacing: "-0.6px",
                    lineHeight: "20px",
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
                    lineHeight: "20px",
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
                    fontSize: 20,
                    fontWeight: 550,
                    color: "#262626",
                    letterSpacing: "-0.6px",
                    lineHeight: "20px",
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
              {!isDataVerificationStage && scoresLoading ? (
                <p style={{ color: "#626262", fontSize: 14, marginTop: 24 }}>Загрузка оценок...</p>
              ) : !isDataVerificationStage && sectionScores?.section === "achievements" && sectionScores.items.length > 0 ? (
                <ReviewScoreBlock
                  data={sectionScores}
                  onSave={handleSaveScores}
                  canEdit={permissions.canComment && !data.readOnly}
                  savedByEmail={commissionMe?.email ?? null}
                />
              ) : null}
            </section>
          )}
            </div>
          )}

          {permissions.canMove && !data.readOnly ? (
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
