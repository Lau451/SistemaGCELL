/**
 * Sign derivation for stock movements (design.md Decision 7): the admin
 * always enters a positive magnitude; `restock`/`return` are always `+`,
 * `sale`/`breakage` are always `-`, and `direction` is honoured ONLY for
 * `adjustment` — for every other type `direction` is ignored, so a
 * wrong-sign submission is unreachable through the UI. Pure function, no
 * side effects.
 *
 * Deliberately NOT in `actions.ts`: that file is `"use server"`, and
 * Next.js requires every export from a Server Actions file to be an
 * async function — a plain sync helper there fails the build.
 */
export type MovementDirection = "increase" | "decrease";

const POSITIVE_MOVEMENT_TYPES = new Set(["restock", "return"]);
const NEGATIVE_MOVEMENT_TYPES = new Set(["sale", "breakage"]);

export function signedQuantityDelta(
  movementType: string,
  magnitude: number,
  direction: MovementDirection,
): number {
  if (POSITIVE_MOVEMENT_TYPES.has(movementType)) {
    return magnitude;
  }
  if (NEGATIVE_MOVEMENT_TYPES.has(movementType)) {
    return -magnitude;
  }
  // `adjustment` (and any unrecognized type — the domain rejects it with
  // 422, not this function) — sign follows the explicit `direction`.
  return direction === "decrease" ? -magnitude : magnitude;
}
