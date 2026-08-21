import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  dayFromParam,
  isInvertedRange,
  presetRange,
  toSinceParam,
  toUntilParam,
} from "./stock-history-dates";

/**
 * Pure day <-> offset-aware-instant conversion (design.md DD1). Covered
 * under BOTH a mocked negative offset (GCELL's UTC-03) AND a mocked
 * positive offset (e.g. UTC+02) — the design explicitly calls out testing
 * a positive-offset timezone, since a raw `+HH:MM` in a query string
 * decodes to a space if not built through `URLSearchParams` downstream.
 */

const UTC_MINUS_3_OFFSET_MINUTES = 180; // getTimezoneOffset(): + west of UTC
const UTC_PLUS_2_OFFSET_MINUTES = -120; // getTimezoneOffset(): - east of UTC

function mockTimezoneOffset(offsetMinutes: number) {
  vi.spyOn(Date.prototype, "getTimezoneOffset").mockReturnValue(
    offsetMinutes,
  );
}

describe("stock-history-dates", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  describe("toSinceParam / toUntilParam", () => {
    it("builds a whole-day-start instant under a negative (UTC-03) offset", () => {
      mockTimezoneOffset(UTC_MINUS_3_OFFSET_MINUTES);

      expect(toSinceParam("2026-08-15")).toBe(
        "2026-08-15T00:00:00.000000-03:00",
      );
    });

    it("builds a whole-day-end instant, inclusive to the microsecond, under a negative offset", () => {
      mockTimezoneOffset(UTC_MINUS_3_OFFSET_MINUTES);

      expect(toUntilParam("2026-08-15")).toBe(
        "2026-08-15T23:59:59.999999-03:00",
      );
    });

    it("builds a whole-day-start instant under a positive (UTC+02) offset", () => {
      mockTimezoneOffset(UTC_PLUS_2_OFFSET_MINUTES);

      expect(toSinceParam("2026-08-15")).toBe(
        "2026-08-15T00:00:00.000000+02:00",
      );
    });

    it("builds a whole-day-end instant under a positive offset", () => {
      mockTimezoneOffset(UTC_PLUS_2_OFFSET_MINUTES);

      expect(toUntilParam("2026-08-15")).toBe(
        "2026-08-15T23:59:59.999999+02:00",
      );
    });

    it("pads a sub-hour offset (e.g. UTC+05:30) to two digits on both sides", () => {
      mockTimezoneOffset(-330);

      expect(toSinceParam("2026-08-15")).toBe(
        "2026-08-15T00:00:00.000000+05:30",
      );
    });

    it("rejects a non YYYY-MM-DD day string", () => {
      mockTimezoneOffset(UTC_MINUS_3_OFFSET_MINUTES);

      expect(() => toSinceParam("2026-8-15")).toThrow(RangeError);
    });
  });

  describe("dayFromParam", () => {
    it("round-trips the day portion out of a since-shaped param", () => {
      expect(dayFromParam("2026-08-15T00:00:00.000000-03:00")).toBe(
        "2026-08-15",
      );
    });

    it("round-trips the day portion out of an until-shaped param", () => {
      expect(dayFromParam("2026-08-15T23:59:59.999999+02:00")).toBe(
        "2026-08-15",
      );
    });
  });

  describe("presetRange", () => {
    beforeEach(() => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date(2026, 7, 15)); // 2026-08-15, local wall clock
    });

    it("today: since and until are both the current local day, negative offset", () => {
      mockTimezoneOffset(UTC_MINUS_3_OFFSET_MINUTES);

      expect(presetRange("today")).toEqual({
        since: "2026-08-15T00:00:00.000000-03:00",
        until: "2026-08-15T23:59:59.999999-03:00",
      });
    });

    it("last7: since is 6 local days before today (7 calendar days inclusive)", () => {
      mockTimezoneOffset(UTC_MINUS_3_OFFSET_MINUTES);

      expect(presetRange("last7")).toEqual({
        since: "2026-08-09T00:00:00.000000-03:00",
        until: "2026-08-15T23:59:59.999999-03:00",
      });
    });

    it("last30: since is 29 local days before today (30 calendar days inclusive)", () => {
      mockTimezoneOffset(UTC_MINUS_3_OFFSET_MINUTES);

      expect(presetRange("last30")).toEqual({
        since: "2026-07-17T00:00:00.000000-03:00",
        until: "2026-08-15T23:59:59.999999-03:00",
      });
    });

    it("last7 under a positive offset produces a percent-encodable, not-yet-space-corrupted offset", () => {
      mockTimezoneOffset(UTC_PLUS_2_OFFSET_MINUTES);

      expect(presetRange("last7")).toEqual({
        since: "2026-08-09T00:00:00.000000+02:00",
        until: "2026-08-15T23:59:59.999999+02:00",
      });
    });

    it("today: crossing a month boundary at the local day itself is unaffected (no day-back arithmetic)", () => {
      vi.setSystemTime(new Date(2026, 8, 1)); // 2026-09-01
      mockTimezoneOffset(UTC_MINUS_3_OFFSET_MINUTES);

      expect(presetRange("today")).toEqual({
        since: "2026-09-01T00:00:00.000000-03:00",
        until: "2026-09-01T23:59:59.999999-03:00",
      });
    });

    it("last7 crosses a month boundary correctly", () => {
      vi.setSystemTime(new Date(2026, 8, 3)); // 2026-09-03
      mockTimezoneOffset(UTC_MINUS_3_OFFSET_MINUTES);

      expect(presetRange("last7")).toEqual({
        since: "2026-08-28T00:00:00.000000-03:00",
        until: "2026-09-03T23:59:59.999999-03:00",
      });
    });
  });

  describe("isInvertedRange", () => {
    it("is false when since is strictly before until", () => {
      expect(
        isInvertedRange(
          "2026-08-01T00:00:00.000000-03:00",
          "2026-08-15T23:59:59.999999-03:00",
        ),
      ).toBe(false);
    });

    it("is false when since equals until (a single-day range is valid)", () => {
      const day = "2026-08-15T00:00:00.000000-03:00";
      expect(isInvertedRange(day, day)).toBe(false);
    });

    it("is true when since is lexically after until", () => {
      expect(
        isInvertedRange(
          "2026-08-20T00:00:00.000000-03:00",
          "2026-08-10T23:59:59.999999-03:00",
        ),
      ).toBe(true);
    });

    it("is false when either side is missing", () => {
      expect(isInvertedRange(undefined, "2026-08-10T00:00:00.000000-03:00")).toBe(
        false,
      );
      expect(isInvertedRange("2026-08-10T00:00:00.000000-03:00", undefined)).toBe(
        false,
      );
      expect(isInvertedRange(undefined, undefined)).toBe(false);
    });
  });
});
