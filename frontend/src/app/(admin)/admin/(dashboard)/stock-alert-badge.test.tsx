import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `StockAlertBadge` — async Server Component rendered inside the "Stock"
 * nav link. Fetches `/api/admin/stock?below=5` (fixed, inclusive threshold,
 * proposal.md D2/D5) using the exact `fetchAdminStock` cookie-forwarding
 * idiom from `stock/page.tsx`. Never throws (design.md Decision 2): a
 * network error, a non-ok response, and a malformed body all collapse to
 * `null`, the same render as a genuine zero count (D6).
 */

vi.mock("next/headers", () => ({
  headers: vi.fn(
    async () =>
      new Headers({ host: "localhost:3000", cookie: "sb-access-token=abc" }),
  ),
}));

async function importBadge() {
  const mod = await import("./stock-alert-badge");
  return mod.StockAlertBadge;
}

describe("StockAlertBadge", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("fetches /api/admin/stock?below=5 forwarding the request cookie", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    } as Response);

    const StockAlertBadge = await importBadge();
    await StockAlertBadge();

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [requestUrl, requestInit] = fetchSpy.mock.calls[0];
    expect(String(requestUrl)).toBe(
      "http://localhost:3000/api/admin/stock?below=5",
    );
    expect(
      (requestInit as RequestInit | undefined)?.headers,
    ).toMatchObject({ cookie: "sb-access-token=abc" });
  });

  it("renders (3) with text-destructive when 3 rows are returned", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([{}, {}, {}]),
    } as Response);

    const StockAlertBadge = await importBadge();
    const jsx = await StockAlertBadge();
    render(jsx);

    const badge = screen.getByText("(3)");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass("text-destructive");
  });

  it("returns null when zero rows are returned", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    } as Response);

    const StockAlertBadge = await importBadge();
    const jsx = await StockAlertBadge();

    expect(jsx).toBeNull();
  });

  it("returns null when fetch rejects (network error)", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network down"));

    const StockAlertBadge = await importBadge();
    const jsx = await StockAlertBadge();

    expect(jsx).toBeNull();
  });

  it("returns null when the response is not ok (e.g. 401)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ error: "unauthenticated" }),
    } as Response);

    const StockAlertBadge = await importBadge();
    const jsx = await StockAlertBadge();

    expect(jsx).toBeNull();
  });

  it("returns null when the response body fails to parse", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () => {
        throw new Error("malformed body");
      },
    } as unknown as Response);

    const StockAlertBadge = await importBadge();
    const jsx = await StockAlertBadge();

    expect(jsx).toBeNull();
  });
});
