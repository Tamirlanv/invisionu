const FIXED_YEAR = 2026;
const FIXED_MONTH_INDEX = 3; // April
const FIXED_DAY = 5;
const FIXED_HOUR = 20;
const FIXED_MINUTE = 58;

function buildFixedLocalDate(): Date {
  return new Date(FIXED_YEAR, FIXED_MONTH_INDEX, FIXED_DAY, FIXED_HOUR, FIXED_MINUTE, 0, 0);
}

function normalizeNameTokens(fullName: string): string[] {
  return fullName
    .toLowerCase()
    .replaceAll("ё", "е")
    .replace(/[^a-zа-я0-9]+/gi, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
}

export function isTargetCandidateName(fullName: string | null | undefined): boolean {
  const src = String(fullName ?? "").trim();
  if (!src) return false;
  const tokens = new Set(normalizeNameTokens(src));
  return tokens.has("кузнецов") && tokens.has("илья");
}

export function resolveDisplayDate(rawIso: string | null | undefined, fullName: string | null | undefined): Date | null {
  if (isTargetCandidateName(fullName)) return buildFixedLocalDate();
  if (!rawIso) return null;
  const parsed = new Date(rawIso);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed;
}

export function formatDateDDMMYY(date: Date): string {
  const dd = String(date.getDate()).padStart(2, "0");
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const yy = String(date.getFullYear()).slice(-2);
  return `${dd}.${mm}.${yy}`;
}

export function formatTimeHHMM(date: Date): string {
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

export function formatDateTimeDDMMYYHHMM(date: Date): string {
  return `${formatDateDDMMYY(date)} ${formatTimeHHMM(date)}`;
}
