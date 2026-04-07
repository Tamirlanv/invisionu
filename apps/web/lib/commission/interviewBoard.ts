import type { InterviewBoardCard, InterviewBoardColumn } from "./interviewTypes";
import { resolveDisplayDate } from "./candidate-timestamp-override";

function startOfLocalDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function localDayKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function parseLocalDayKey(key: string): Date {
  const [y, m, d] = key.split("-").map((x) => Number(x));
  return new Date(y, (m ?? 1) - 1, d ?? 1);
}

/** Заголовок колонки по дате: «Сегодня», «Завтра» или «3 апреля» */
export function formatInterviewColumnTitle(slotDate: Date, today: Date): string {
  const t0 = startOfLocalDay(today).getTime();
  const tSlot = startOfLocalDay(slotDate).getTime();
  const dayMs = 86400000;
  const delta = tSlot - t0;
  if (delta === 0) return "Сегодня";
  if (delta === dayMs) return "Завтра";
  return new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" }).format(slotDate);
}

function formatTimeFromIso(iso: string | null | undefined, candidateFullName: string): string | null {
  if (!iso || typeof iso !== "string") return null;
  const d = resolveDisplayDate(iso, candidateFullName);
  if (!d) return null;
  return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

export function mapApiRowToInterviewCard(row: Record<string, unknown>): InterviewBoardCard {
  const scheduledIso = asStr(row.interview_scheduled_at_iso);
  const candidateFullName = String(row.candidate_full_name ?? "");
  const visual = asStr(row.visual_status);
  return {
    applicationId: String(row.application_id ?? ""),
    candidateFullName,
    line1: String(row.program ?? "") || "—",
    line2: String(row.education_track ?? "") || "—",
    timeLabel: formatTimeFromIso(scheduledIso, candidateFullName),
    action: scheduledIso ? "interview" : "assign_date",
    highlight: visual === "positive",
    scheduledAtIso: scheduledIso,
  };
}

function asStr(v: unknown): string | null {
  if (v == null) return null;
  const s = String(v);
  return s.length ? s : null;
}

/**
 * Группирует карточки этапа interview в колонки: без даты → «Назначить», с датой → по календарным дням.
 * Колонки «Сегодня» и «Завтра» всегда присутствуют (даже без карточек), затем остальные дни с назначениями.
 */
export function buildInterviewColumns(cards: InterviewBoardCard[], now: Date = new Date()): InterviewBoardColumn[] {
  const assign: InterviewBoardCard[] = [];
  const byDay = new Map<string, InterviewBoardCard[]>();

  for (const c of cards) {
    if (!c.scheduledAtIso) {
      assign.push(c);
      continue;
    }
    const displayDate = resolveDisplayDate(c.scheduledAtIso, c.candidateFullName);
    if (!displayDate || isNaN(displayDate.getTime())) {
      assign.push(c);
      continue;
    }
    const key = localDayKey(displayDate);
    const list = byDay.get(key) ?? [];
    list.push(c);
    byDay.set(key, list);
  }

  const todayStart = startOfLocalDay(now);
  const todayKey = localDayKey(todayStart);
  const tomorrowStart = new Date(todayStart.getTime() + 86400000);
  const tomorrowKey = localDayKey(tomorrowStart);

  const dayKeys = [...byDay.keys()].sort();
  const otherDayKeys = dayKeys.filter((k) => k !== todayKey && k !== tomorrowKey);

  const columns: InterviewBoardColumn[] = [
    {
      id: "assign",
      title: "Назначить",
      cards: assign,
    },
    {
      id: `day-${todayKey}`,
      title: "Сегодня",
      cards: byDay.get(todayKey) ?? [],
    },
    {
      id: `day-${tomorrowKey}`,
      title: "Завтра",
      cards: byDay.get(tomorrowKey) ?? [],
    },
  ];

  for (const key of otherDayKeys) {
    const slotDate = parseLocalDayKey(key);
    const title = formatInterviewColumnTitle(slotDate, now);
    columns.push({
      id: `day-${key}`,
      title,
      cards: byDay.get(key) ?? [],
    });
  }

  return columns;
}
