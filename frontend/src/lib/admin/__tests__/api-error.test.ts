import { describe, expect, it } from "vitest";
import { extractAdminError } from "../api-error";

/**
 * `extractAdminError` — normalizes FastAPI's two `422` body shapes into
 * one user-facing message, per design.md's "Decision: `422` for every
 * rejected body; no `400`": Pydantic's own native list-of-errors shape
 * (produced for schema/type failures like `extra="forbid"`) and this
 * app's own `{"detail": "string"}` shape (produced by `_execute_or_raise`
 * for a domain `ValueError`/`TypeError` escaping a use case).
 */

describe("extractAdminError", () => {
  it("extracts the message from Pydantic's native list-of-errors shape", () => {
    const body = {
      detail: [
        {
          type: "extra_forbidden",
          loc: ["body", "slug"],
          msg: "Extra inputs are not permitted",
          input: "funda-iphone-15",
        },
      ],
    };

    expect(extractAdminError(422, body)).toBe(
      "Extra inputs are not permitted",
    );
  });

  it("joins multiple Pydantic error messages", () => {
    const body = {
      detail: [
        { type: "missing", loc: ["body", "name"], msg: "Field required" },
        { type: "missing", loc: ["body", "model"], msg: "Field required" },
      ],
    };

    expect(extractAdminError(422, body)).toBe("Field required; Field required");
  });

  it("returns the string verbatim for this app's own {detail: string} shape", () => {
    const body = { detail: "ProductVariant.price cannot be negative" };

    expect(extractAdminError(422, body)).toBe(
      "ProductVariant.price cannot be negative",
    );
  });

  it("returns the string verbatim for a 409 slug_conflict body", () => {
    const body = { detail: "slug_conflict" };

    expect(extractAdminError(409, body)).toBe("slug_conflict");
  });

  it("falls back to a generic message for an unrecognized body shape", () => {
    expect(extractAdminError(500, { unexpected: true })).toBe(
      "Something went wrong. Please try again.",
    );
  });

  it("falls back to a generic message for a null or non-object body", () => {
    expect(extractAdminError(500, null)).toBe(
      "Something went wrong. Please try again.",
    );
    expect(extractAdminError(500, "plain text body")).toBe(
      "Something went wrong. Please try again.",
    );
  });
});
