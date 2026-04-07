"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Image from "next/image";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { PillSegmentedControl } from "@/components/application/PillSegmentedControl";
import { CommissionSidebar } from "@/components/commission/CommissionSidebar";
import {
  downloadCommissionApplicationDocument,
  getCommissionApplicationPersonalInfo,
  openCommissionApplicationDocumentInNewTab,
  searchCommissionApplicationsForDocuments,
} from "@/lib/commission/query";
import { getCommissionCardBorderStyle } from "@/lib/commission/cardBorder";
import { formatDateDDMMYY, resolveDisplayDate } from "@/lib/commission/candidate-timestamp-override";
import { filterDocumentsForCategory, type DocumentCategoryFilter } from "@/lib/commission/documentsFilters";
import { useCommissionSidebarOpen } from "@/lib/commission/use-commission-sidebar-open";
import type { CommissionApplicationPersonalInfoView, CommissionBoardApplicationCard } from "@/lib/commission/types";
import shellStyles from "../page.module.css";
import styles from "./page.module.css";

const FILTER_ORDER: { key: DocumentCategoryFilter; label: string }[] = [
  { key: "all", label: "Все" },
  { key: "identity", label: "Удостоверение / паспорт" },
  { key: "presentation", label: "Презентация" },
  { key: "english", label: "IELTS/TOEFL" },
  { key: "ent_nis", label: "ЕНТ/НИШ 12 классов" },
];

function formatProgramLabel(raw: string | null | undefined): string {
  if (!raw) return "";
  const t = raw.trim();
  if (t === "Бакалавриат") return "Бакалавр";
  return t;
}

function commissionDocCardBorderClass(
  tone: string | undefined,
  map: typeof styles,
): string {
  if (tone === "green") return map.docCardGreen;
  if (tone === "red") return map.docCardRed;
  return map.docCardNeutral;
}

function formatSubmittedDate(raw: string | null | undefined, candidateFullName: string): string {
  if (!raw) return "—";
  const d = resolveDisplayDate(raw, candidateFullName);
  if (!d) return raw;
  return formatDateDDMMYY(d);
}

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return v;
}

export default function CommissionDocumentsPage() {
  return (
    <Suspense fallback={<p className="muted">Загрузка…</p>}>
      <DocumentsPageInner />
    </Suspense>
  );
}

function DocumentsPageInner() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { isSidebarOpen, setIsSidebarOpen } = useCommissionSidebarOpen();
  const [program, setProgram] = useState<string | null>(params.get("program"));
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounced(search, 350);

  const [results, setResults] = useState<CommissionBoardApplicationCard[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [personal, setPersonal] = useState<CommissionApplicationPersonalInfoView | null>(null);
  const [personalLoading, setPersonalLoading] = useState(false);
  const [personalError, setPersonalError] = useState<string | null>(null);
  const [docActionError, setDocActionError] = useState<string | null>(null);

  const [docFilter, setDocFilter] = useState<DocumentCategoryFilter>("all");

  useEffect(() => {
    setProgram(params.get("program"));
  }, [params]);

  useEffect(() => {
    const next = new URLSearchParams(params.toString());
    if (program) next.set("program", program);
    else next.delete("program");
    const qs = next.toString();
    const target = `${pathname}${qs ? `?${qs}` : ""}`;
    const current = `${pathname}${params.toString() ? `?${params.toString()}` : ""}`;
    if (target !== current) {
      router.replace(target);
    }
  }, [program, params, pathname, router]);

  useEffect(() => {
    const q = debouncedSearch.trim();
    if (!q) {
      setResults([]);
      setSearchError(null);
      setSearchLoading(false);
      setSelectedId(null);
      setPersonal(null);
      return;
    }
    let cancelled = false;
    setSearchLoading(true);
    setSearchError(null);
    void searchCommissionApplicationsForDocuments(q)
      .then((rows) => {
        if (cancelled) return;
        setResults(rows);
        setSelectedId((prev) => {
          if (prev && !rows.some((r) => r.applicationId === prev)) {
            setPersonal(null);
            return null;
          }
          return prev;
        });
      })
      .catch((e: unknown) => {
        if (!cancelled) setSearchError(e instanceof Error ? e.message : "Ошибка поиска");
      })
      .finally(() => {
        if (!cancelled) setSearchLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [debouncedSearch]);

  useEffect(() => {
    if (!selectedId) {
      setPersonal(null);
      setDocActionError(null);
      return;
    }
    let cancelled = false;
    setPersonalLoading(true);
    setPersonalError(null);
    void getCommissionApplicationPersonalInfo(selectedId)
      .then((data) => {
        if (!cancelled) setPersonal(data);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setPersonalError(e instanceof Error ? e.message : "Не удалось загрузить данные");
          setPersonal(null);
        }
      })
      .finally(() => {
        if (!cancelled) setPersonalLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  useEffect(() => {
    setDocActionError(null);
  }, [selectedId, docFilter]);

  const filtered = useMemo(() => {
    if (!personal?.personalInfo) return { documents: [] as CommissionApplicationPersonalInfoView["personalInfo"]["documents"], showVideo: false };
    const docs = personal.personalInfo.documents ?? [];
    const video = personal.personalInfo.videoPresentation ?? null;
    return filterDocumentsForCategory(docs, video, docFilter);
  }, [personal, docFilter]);

  const leftState = useMemo(() => {
    if (!selectedId) return { kind: "no_candidate" as const };
    if (personalLoading) return { kind: "loading" as const };
    if (personalError) return { kind: "error" as const, text: personalError };
    if (!personal?.personalInfo) return { kind: "loading" as const };
    const videoUrl = personal.personalInfo.videoPresentation?.url?.trim();
    const hasVideo = Boolean(filtered.showVideo && videoUrl);
    const hasDocs = filtered.documents.length > 0;
    if (!hasDocs && !hasVideo) {
      if (docFilter === "all") return { kind: "no_docs_at_all" as const };
      return { kind: "no_docs_for_filter" as const };
    }
    return { kind: "content" as const, hasVideo, videoUrl: videoUrl ?? "" };
  }, [selectedId, personalLoading, personalError, personal, filtered, docFilter]);

  return (
    <div className={shellStyles.shell}>
      <CommissionSidebar isOpen={isSidebarOpen} program={program} onProgramChange={setProgram} />
      <main
        className={`${shellStyles.page} ${isSidebarOpen ? shellStyles.pageWithSidebar : shellStyles.pageWithSidebarCollapsed}`}
      >
        <button
          type="button"
          className={shellStyles.sidebarToggle}
          onClick={() => setIsSidebarOpen((v) => !v)}
          aria-label="Toggle sidebar"
        >
          <Image src="/assets/icons/icon_sidebar.svg" alt="" width={24} height={24} />
        </button>

        <div className={styles.titleRow}>
          <h1 className={styles.title}>Документы</h1>
          <div className={styles.filterPillsScroll}>
            <PillSegmentedControl<DocumentCategoryFilter>
              gap="tabs"
              aria-label="Тип документа"
              options={FILTER_ORDER.map(({ key, label }) => ({ value: key, label }))}
              value={docFilter}
              onChange={setDocFilter}
            />
          </div>
        </div>

        <div className={styles.splitWrap}>
          <div className={styles.splitCard}>
            <section className={styles.panelLeft} aria-label="Документы выбранного кандидата">
              {leftState.kind === "no_candidate" && (
                <div className={styles.emptyCenter}>
                  <Image
                    className={styles.emptyIcon}
                    src="/assets/icons/solar_file-bold.svg"
                    alt=""
                    width={50}
                    height={50}
                    aria-hidden
                  />
                  <p className={styles.emptyTitle}>Выберите кандидата</p>
                </div>
              )}
              {leftState.kind === "loading" && <p className={styles.loadingText}>Загрузка документов…</p>}
              {leftState.kind === "error" && <p className={styles.errorText}>{leftState.text}</p>}
              {docActionError ? <p className={styles.errorText}>{docActionError}</p> : null}
              {leftState.kind === "no_docs_for_filter" && (
                <div className={styles.emptyCenter}>
                  <p className={styles.emptyTitle}>Документы выбранного типа не найдены</p>
                </div>
              )}
              {leftState.kind === "no_docs_at_all" && (
                <div className={styles.emptyCenter}>
                  <p className={styles.emptyTitle}>Нет прикреплённых документов для этой заявки</p>
                </div>
              )}
              {leftState.kind === "content" && personal && (
                <div style={{ width: "100%" }}>
                  {leftState.hasVideo ? (
                    <div
                      className={`${styles.docCard} ${commissionDocCardBorderClass(
                        personal.personalInfo.videoPresentation?.borderTone === "green" ? "green" : "gray",
                        styles,
                      )}`}
                    >
                      <div className={styles.docCardBody}>
                        <p className={styles.docCardTitle}>Видео-презентация</p>
                        <div className={styles.docCardSubtitleRow}>
                          <p className={styles.docCardSubtitle}>{leftState.videoUrl}</p>
                          <button
                            type="button"
                            className={styles.docCardCopy}
                            aria-label="Копировать ссылку"
                            onClick={() => {
                              void navigator.clipboard.writeText(leftState.videoUrl);
                            }}
                          >
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
                              <path
                                d="M8 7V5a2 2 0 012-2h8a2 2 0 012 2v10a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2M8 7h8a2 2 0 012 2v2"
                                stroke="#626262"
                                strokeWidth="1.5"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                              />
                            </svg>
                          </button>
                        </div>
                      </div>
                      <div className={styles.docCardActions}>
                        <button
                          type="button"
                          className={styles.docBtnOpen}
                          onClick={() => {
                            window.open(leftState.videoUrl, "_blank", "noopener,noreferrer");
                          }}
                        >
                          Открыть
                        </button>
                        <button
                          type="button"
                          className={styles.docBtnDownload}
                          onClick={() => {
                            void navigator.clipboard.writeText(leftState.videoUrl);
                          }}
                        >
                          Скопировать ссылку
                        </button>
                      </div>
                    </div>
                  ) : null}
                  {filtered.documents.length > 0 ? (
                    <ul
                      className={`${styles.docList} ${leftState.hasVideo ? styles.docListAfterVideo : ""}`}
                    >
                      {filtered.documents.map((d) => (
                        <li
                          key={d.id}
                          className={`${styles.docCard} ${commissionDocCardBorderClass(d.borderTone, styles)}`}
                        >
                          <div className={styles.docCardBody}>
                            <p className={styles.docCardTitle}>{d.type}</p>
                            <p className={styles.docCardSubtitleAlone}>{d.fileName}</p>
                          </div>
                          <div className={styles.docCardActions}>
                            <button
                              type="button"
                              className={styles.docBtnOpen}
                              onClick={() => {
                                void (async () => {
                                  try {
                                    setDocActionError(null);
                                    await openCommissionApplicationDocumentInNewTab(selectedId!, d.id);
                                  } catch (error) {
                                    setDocActionError(
                                      error instanceof Error ? error.message : "Не удалось открыть документ",
                                    );
                                  }
                                })();
                              }}
                            >
                              Открыть
                            </button>
                            <button
                              type="button"
                              className={styles.docBtnDownload}
                              onClick={() => {
                                void (async () => {
                                  try {
                                    setDocActionError(null);
                                    await downloadCommissionApplicationDocument(selectedId!, d.id, d.fileName);
                                  } catch (error) {
                                    setDocActionError(
                                      error instanceof Error ? error.message : "Не удалось скачать документ",
                                    );
                                  }
                                })();
                              }}
                            >
                              Скачать
                            </button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              )}
            </section>

            <div className={styles.divider} aria-hidden />

            <aside className={styles.panelRight} aria-label="Поиск кандидата">
              <div className={styles.searchRow}>
                <div className={styles.searchInputWrap}>
                  <input
                    type="search"
                    className={styles.searchInput}
                    placeholder="Поиск по имени и контактам кандидата"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    autoComplete="off"
                  />
                  <span className={styles.searchIcon} aria-hidden>
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                      <path
                        fillRule="evenodd"
                        clipRule="evenodd"
                        d="M6.25 1.75C3.62665 1.75 1.5 3.87665 1.5 6.5C1.5 9.12335 3.62665 11.25 6.25 11.25C7.31667 11.25 8.30139 10.9143 9.11367 10.3475L12.2803 13.5142L13.3475 12.447L10.1808 9.28033C10.7475 8.46805 11.0833 7.48333 11.0833 6.41667C11.0833 3.79332 8.95668 1.66667 6.33333 1.66667H6.25V1.75ZM2.91667 6.5C2.91667 4.65905 4.40905 3.16667 6.25 3.16667C8.09095 3.16667 9.58333 4.65905 9.58333 6.5C9.58333 8.34095 8.09095 9.83333 6.25 9.83333C4.40905 9.83333 2.91667 8.34095 2.91667 6.5Z"
                        fill="#262626"
                        fillOpacity="0.3"
                      />
                    </svg>
                  </span>
                </div>
                <span aria-hidden style={{ opacity: 0.8 }}>
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path
                      d="M2 4h12M4 8h8M6 12h4"
                      stroke="#262626"
                      strokeOpacity="0.8"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                    />
                  </svg>
                </span>
              </div>

              {!debouncedSearch.trim() ? (
                <p className={styles.rightHint}>
                  Введите в поисковую строку имя или контакты ученика, документы которого вам нужны
                </p>
              ) : null}

              {searchError ? <p className={styles.errorText}>{searchError}</p> : null}
              {searchLoading ? <p className={styles.loadingText}>Поиск…</p> : null}

              {!searchLoading && debouncedSearch.trim() && !searchError && results.length === 0 ? (
                <p className={styles.emptyHint}>По вашему запросу кандидаты не найдены</p>
              ) : null}

              <div className={styles.resultsList}>
                {results.map((card) => {
                  const selected = selectedId === card.applicationId;
                  return (
                    <button
                      key={card.applicationId}
                      type="button"
                      className={`${styles.resultCard} ${selected ? styles.resultCardSelected : ""}`}
                      style={{ border: getCommissionCardBorderStyle(card.currentStage, card) }}
                      onClick={() => setSelectedId(card.applicationId)}
                    >
                      <span className={styles.resultName}>{card.candidateFullName || "Кандидат"}</span>
                      <div className={styles.resultRow}>
                        <div className={styles.resultColLeft}>
                          {card.program ? <span>{formatProgramLabel(card.program)}</span> : null}
                          {card.age != null ? <span>{card.age} лет</span> : null}
                        </div>
                        <div className={styles.resultColRight}>
                          <span>{formatSubmittedDate(card.submittedAt, card.candidateFullName)}</span>
                          {card.city ? <span>{card.city}</span> : null}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </aside>
          </div>
        </div>
      </main>
    </div>
  );
}
