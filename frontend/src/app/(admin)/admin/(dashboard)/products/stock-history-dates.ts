/**
 * Pure day <-> offset-aware-instant conversion for the movement-history
 * date filter (design.md DD1). `created_at` is `timestamptz`; the admin's
 * calendar lives in the browser, so a selected day like `"2026-08-15"` is
 * converted to a browser-local day boundary, carried on the wire as a
 * full ISO-8601 instant with an explicit UTC offset — never a bare date
 * string (which the backend would have to reinterpret using the SERVER's
 * timezone, not the browser's).
 *
 * The offset is resolved PER selected date via
 * `Date.prototype.getTimezoneOffset()`, so DST transitions are handled
 * for free — no manual DST table. Microseconds are written directly into
 * the string, not derived from a JS `Date` (whose precision stops at
 * milliseconds), so `until` reads `...T23:59:59.999999<offset>` with zero
 * truncation gap before the next local midnight at Postgres' microsecond
 * resolution.
 *
 * Deliberately NOT in `stock-history.tsx`: same "pure helper out of the
 * component" precedent as commit 4881583's `stock-movement-sign.ts`.
 *
 * **Encoding gotcha** (design.md "Interfaces / Contracts"): a raw
 * `+HH:MM` offset in a query string decodes to a space. Every caller of
 * these strings MUST build the query with `URLSearchParams`, never
 * string concatenation.
 */

const DAY_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

function assertDay(day: string): void {
  if (!DAY_PATTERN.test(day)) {
    throw new RangeError(`Expected a "YYYY-MM-DD" day string, got: ${day}`);
  }
}

/**
 * `getTimezoneOffset()` returns minutes the local zone is BEHIND UTC
 * (positive for GCELL's UTC-03), so the sign is inverted to build the
 * ISO offset string: a positive offset-minutes value produces a `-`
 * sign, a negative value produces a `+` sign.
 */
function localOffsetSuffix(day: string): string {
  const offsetMinutes = new Date(`${day}T00:00:00`).getTimezoneOffset();
  const sign = offsetMinutes > 0 ? "-" : "+";
  const absoluteMinutes = Math.abs(offsetMinutes);
  const hours = String(Math.floor(absoluteMinutes / 60)).padStart(2, "0");
  const minutes = String(absoluteMinutes % 60).padStart(2, "0");
  return `${sign}${hours}:${minutes}`;
}

export function toSinceParam(day: string): string {
  assertDay(day);
  return `${day}T00:00:00.000000${localOffsetSuffix(day)}`;
}

export function toUntilParam(day: string): string {
  assertDay(day);
  return `${day}T23:59:59.999999${localOffsetSuffix(day)}`;
}

/**
 * Redisplay in `<input type="date">`: the wire format always begins with
 * the `"YYYY-MM-DD"` day, regardless of which end (`since`/`until`) or
 * offset produced it.
 */
export function dayFromParam(param: string): string {
  return param.slice(0, 10);
}

function todayLocalDay(): string {
  return formatLocalDay(new Date());
}

function formatLocalDay(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function addLocalDays(day: string, deltaDays: number): string {
  assertDay(day);
  const [year, month, date] = day.split("-").map(Number);
  return formatLocalDay(new Date(year, month - 1, date + deltaDays));
}

const PRESET_DAYS_BACK: Record<"today" | "last7" | "last30", number> = {
  // D15: "last N days" = today plus (N-1) days back, N calendar days total
  // INCLUSIVE of today.
  today: 0,
  last7: 6,
  last30: 29,
};

export function presetRange(
  preset: "today" | "last7" | "last30",
): { since: string; until: string } {
  const today = todayLocalDay();
  const sinceDay = addLocalDays(today, -PRESET_DAYS_BACK[preset]);
  return { since: toSinceParam(sinceDay), until: toUntilParam(today) };
}

/**
 * Both wire-format strings share the same fixed-width ISO-8601 shape, so
 * a plain lexical comparison is equivalent to instant comparison
 * (design.md "Interfaces / Contracts"). Either side missing is never
 * "inverted" — a one-sided filter is always valid.
 */
export function isInvertedRange(since?: string, until?: string): boolean {
  if (!since || !until) {
    return false;
  }
  return since > until;
}
