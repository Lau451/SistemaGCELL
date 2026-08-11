/**
 * Normalizes FastAPI's two rejected-body shapes into one user-facing
 * message, per design.md's "Decision: `422` for every rejected body; no
 * `400`": Pydantic's own native list-of-errors shape (`{"detail": [...]}`
 * — produced for schema/type failures like `extra="forbid"` rejecting a
 * client-supplied `slug`) and this app's own `{"detail": "string"}` shape
 * (produced by `admin.py`'s `_execute_or_raise` for a domain
 * `ValueError`/`TypeError` escaping a use case, and for the `409`
 * `slug_conflict` body). Any other/unrecognized shape falls back to a
 * generic message rather than surfacing `undefined` or `[object Object]`.
 *
 * `status` is accepted (design.md's exact `extractAdminError(status,
 * body)` signature) but not currently branched on — every mapped status
 * (`404`, `409`, `422`) already carries a self-describing `detail`.
 */

const GENERIC_ADMIN_ERROR_MESSAGE = "Something went wrong. Please try again.";

interface FastApiValidationErrorItem {
  msg: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isValidationErrorItem(
  value: unknown,
): value is FastApiValidationErrorItem {
  return isRecord(value) && typeof value.msg === "string";
}

export function extractAdminError(status: number, body: unknown): string {
  void status;

  if (!isRecord(body) || !("detail" in body)) {
    return GENERIC_ADMIN_ERROR_MESSAGE;
  }

  const { detail } = body;

  if (typeof detail === "string" && detail.length > 0) {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const messages = detail
      .filter(isValidationErrorItem)
      .map((item) => item.msg);
    if (messages.length > 0) {
      return messages.join("; ");
    }
  }

  return GENERIC_ADMIN_ERROR_MESSAGE;
}
