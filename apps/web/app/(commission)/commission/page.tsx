"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import Image from "next/image";
import { CommissionSidebar } from "@/components/commission/CommissionSidebar";
import { BoardToolbar } from "@/components/commission/BoardToolbar";
import { MetricsRow } from "@/components/commission/MetricsRow";
import { BoardContainer } from "@/components/commission/BoardContainer";
import { getBoardMetrics, rangeFromQuery } from "@/lib/commission/query";
import type { CommissionBoardFilters, CommissionBoardMetrics, CommissionRange } from "@/lib/commission/types";
import styles from "./page.module.css";

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return v;
}

export default function CommissionPage() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const [search, setSearch] = useState(params.get("search") ?? "");
  const [program, setProgram] = useState<string | null>(params.get("program"));
  const [range, setRange] = useState<CommissionRange>(rangeFromQuery(params.get("range")));
  const [metrics, setMetrics] = useState<CommissionBoardMetrics>({
    totalApplications: 0,
    todayApplications: 0,
    needsAttention: 0,
    aiRecommended: 0,
  });
  const [msg, setMsg] = useState<string | null>(null);

  const debouncedSearch = useDebounced(search, 350);

  const filters: CommissionBoardFilters = useMemo(
    () => ({ search: debouncedSearch, program, range }),
    [debouncedSearch, program, range],
  );

  useEffect(() => {
    setSearch(params.get("search") ?? "");
    setProgram(params.get("program"));
    setRange(rangeFromQuery(params.get("range")));
  }, [params]);

  useEffect(() => {
    const next = new URLSearchParams(params.toString());
    if (debouncedSearch.trim()) next.set("search", debouncedSearch.trim());
    else next.delete("search");
    if (program) next.set("program", program);
    else next.delete("program");
    next.set("range", range);
    const target = `${pathname}${next.toString() ? `?${next.toString()}` : ""}`;
    if (target !== `${pathname}${params.toString() ? `?${params.toString()}` : ""}`) {
      router.replace(target);
    }
  }, [debouncedSearch, program, range, params, pathname, router]);

  useEffect(() => {
    void (async () => {
      try {
        setMetrics(await getBoardMetrics(filters));
      } catch (e) {
        setMsg(e instanceof Error ? e.message : "Не удалось загрузить метрики");
      }
    })();
  }, [filters]);

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

        <BoardToolbar
          search={search}
          range={range}
          onSearchChange={setSearch}
          onRangeChange={setRange}
        />

        <MetricsRow metrics={metrics} />

        {msg ? <p className="error">{msg}</p> : null}

        <BoardContainer filters={filters} onError={setMsg} />
      </main>
    </div>
  );
}

