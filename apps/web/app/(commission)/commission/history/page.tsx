"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { PillSegmentedControl } from "@/components/application/PillSegmentedControl";
import { CommissionSidebar } from "@/components/commission/CommissionSidebar";
import { HistoryTimeline } from "@/components/commission/HistoryTimeline";
import { HistoryToolbar } from "@/components/commission/HistoryToolbar";
import {
  getArchivedCommissionApplications,
  getCommissionHistoryEvents,
} from "@/lib/commission/query";
import { useCommissionSidebarOpen } from "@/lib/commission/use-commission-sidebar-open";
import type {
  CommissionBoardApplicationCard,
  CommissionHistoryEvent,
  CommissionHistoryEventFilter,
  CommissionHistoryMode,
  CommissionHistorySort,
} from "@/lib/commission/types";
import { formatDateTimeDDMMYYHHMM, resolveDisplayDate } from "@/lib/commission/candidate-timestamp-override";
import styles from "../page.module.css";

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return v;
}

function modeFromQuery(v: string | null): CommissionHistoryMode {
  return v === "archive" ? "archive" : "events";
}

function eventTypeFromQuery(v: string | null): CommissionHistoryEventFilter {
  if (
    v === "all" ||
    v === "commission" ||
    v === "system" ||
    v === "candidates" ||
    v === "stage" ||
    v === "interview" ||
    v === "decision"
  ) {
    return v;
  }
  return "all";
}

function sortFromQuery(v: string | null): CommissionHistorySort {
  return v === "oldest" ? "oldest" : "newest";
}

function formatArchiveUpdatedAt(raw: string | null | undefined, candidateFullName: string): string {
  if (!raw) return "—";
  const overridden = resolveDisplayDate(raw, candidateFullName);
  if (overridden) return formatDateTimeDDMMYYHHMM(overridden);
  return raw;
}

export default function CommissionHistoryPage() {
  return (
    <Suspense>
      <CommissionHistoryInner />
    </Suspense>
  );
}

function CommissionHistoryInner() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { isSidebarOpen, setIsSidebarOpen } = useCommissionSidebarOpen();

  const [mode, setMode] = useState<CommissionHistoryMode>(() => modeFromQuery(params.get("mode")));
  const [search, setSearch] = useState(params.get("search") ?? "");
  const [program, setProgram] = useState<string | null>(params.get("program"));
  const [eventType, setEventType] = useState<CommissionHistoryEventFilter>(() => eventTypeFromQuery(params.get("eventType")));
  const [sort, setSort] = useState<CommissionHistorySort>(() => sortFromQuery(params.get("sort")));

  const [historyItems, setHistoryItems] = useState<CommissionHistoryEvent[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [archiveCards, setArchiveCards] = useState<CommissionBoardApplicationCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);

  const debouncedSearch = useDebounced(search, 350);

  useEffect(() => {
    setMode(modeFromQuery(params.get("mode")));
    setSearch(params.get("search") ?? "");
    setProgram(params.get("program"));
    setEventType(eventTypeFromQuery(params.get("eventType")));
    setSort(sortFromQuery(params.get("sort")));
  }, [params]);

  useEffect(() => {
    const next = new URLSearchParams(params.toString());
    next.set("mode", mode);
    if (debouncedSearch.trim()) next.set("search", debouncedSearch.trim());
    else next.delete("search");
    if (program) next.set("program", program);
    else next.delete("program");
    if (mode === "events") {
      next.set("eventType", eventType);
      next.set("sort", sort);
    } else {
      next.delete("eventType");
      next.delete("sort");
    }

    const target = `${pathname}${next.toString() ? `?${next.toString()}` : ""}`;
    const current = `${pathname}${params.toString() ? `?${params.toString()}` : ""}`;
    if (target !== current) router.replace(target);
  }, [debouncedSearch, eventType, mode, params, pathname, program, router, sort]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setMsg(null);

    void (async () => {
      try {
        if (mode === "archive") {
          const rows = await getArchivedCommissionApplications({
            search: debouncedSearch,
            program,
          });
          if (cancelled) return;
          setArchiveCards(rows);
          setHistoryItems([]);
          setHistoryTotal(0);
          return;
        }

        const payload = await getCommissionHistoryEvents({
          search: debouncedSearch,
          program,
          eventType,
          sort,
        });
        if (cancelled) return;
        setHistoryItems(payload.items);
        setHistoryTotal(payload.total);
        setArchiveCards([]);
      } catch (e) {
        if (cancelled) return;
        setMsg(e instanceof Error ? e.message : "Не удалось загрузить историю");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [debouncedSearch, eventType, mode, program, sort]);

  const subtitle = useMemo(() => {
    if (mode === "archive") {
      return "Архивные заявки внутри вкладки «История»."
    }
    return "Общий журнал действий платформы, кандидатов и комиссии.";
  }, [mode]);

  return (
    <div className={styles.shell}>
      <CommissionSidebar isOpen={isSidebarOpen} program={program} onProgramChange={setProgram} />
      <main
        className={`${styles.page} ${isSidebarOpen ? styles.pageWithSidebar : styles.pageWithSidebarCollapsed}`}
      >
        <button
          type="button"
          className={styles.sidebarToggle}
          onClick={() => setIsSidebarOpen((v) => !v)}
          aria-label="Toggle sidebar"
        >
          <Image src="/assets/icons/icon_sidebar.svg" alt="" width={24} height={24} />
        </button>

        <div style={{ display: "grid", gap: 6 }}>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600 }}>История</h1>
          <p style={{ margin: 0, color: "#626262", fontSize: 14, fontWeight: 350 }}>{subtitle}</p>
        </div>

        <PillSegmentedControl<CommissionHistoryMode>
          aria-label="Режим истории"
          options={[
            { value: "events", label: "События" },
            { value: "archive", label: "Архив" },
          ]}
          value={mode}
          onChange={setMode}
        />

        {mode === "events" ? (
          <HistoryToolbar
            search={search}
            onSearchChange={setSearch}
            eventType={eventType}
            onEventTypeChange={setEventType}
            sort={sort}
            onSortChange={setSort}
          />
        ) : (
          <input
            className="input"
            placeholder="Поиск по архиву"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Поиск по архивным заявкам"
            style={{ maxWidth: 420 }}
          />
        )}

        {msg ? <p style={{ color: "#e53935", margin: 0 }}>{msg}</p> : null}

        {mode === "events" ? (
          <div style={{ display: "grid", gap: 12 }}>
            <p style={{ margin: 0, fontSize: 13, color: "#8b8b8b", fontWeight: 350 }}>
              Событий: {historyTotal}
            </p>
            <HistoryTimeline
              items={historyItems}
              loading={loading}
              emptyText="Пока нет событий для выбранных фильтров."
              linkToCandidate
            />
          </div>
        ) : loading ? (
          <p style={{ margin: 0, fontSize: 14, color: "#626262", fontWeight: 350 }}>Загрузка...</p>
        ) : archiveCards.length === 0 ? (
          <p style={{ margin: 0, fontSize: 14, color: "#626262", fontWeight: 350 }}>Нет архивных заявок.</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 12 }}>
            {archiveCards.map((c) => (
              <li key={c.applicationId}>
                <Link
                  href={`/commission/applications/${c.applicationId}`}
                  style={{
                    display: "block",
                    padding: "16px 20px",
                    borderRadius: 12,
                    border: "1px solid #e8e8e8",
                    background: "#fafafa",
                    textDecoration: "none",
                    color: "#262626",
                  }}
                >
                  <div style={{ fontWeight: 550 }}>{c.candidateFullName}</div>
                  <div style={{ fontSize: 13, color: "#626262", marginTop: 4, fontWeight: 350 }}>
                    {c.program || "—"} · обновлено {formatArchiveUpdatedAt(c.updatedAt, c.candidateFullName)}
                  </div>
                  <div style={{ fontSize: 12, color: "#888", marginTop: 6, fontWeight: 350 }}>Только просмотр</div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
