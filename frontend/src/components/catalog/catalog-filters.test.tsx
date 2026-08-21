import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CatalogFilters } from "./catalog-filters";

/**
 * Client-side search/filter wiring. RTL + user-event, `fetch` spied per
 * design.md's testing strategy ("filter change fetches `/api/catalog`,
 * replaces cards, no navigation").
 */

const INITIAL_ITEMS = [
  {
    slug: "fundas-iphone-15",
    name: "Funda iPhone 15",
    priceFrom: 5000,
    hasPriceRange: false,
    imageUrl: null,
    imageAlt: "Funda iPhone 15",
  },
];

const INITIAL_FILTERS = { models: ["Galaxy S24", "iPhone 15"], colors: ["negro", "transparente"] };

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response;
}

describe("CatalogFilters", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the initial server-fetched cards without calling fetch on mount", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    render(
      <CatalogFilters
        initialItems={INITIAL_ITEMS}
        initialFilters={INITIAL_FILTERS}
      />,
    );

    expect(screen.getByText("Funda iPhone 15")).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("fetches /api/catalog and replaces the rendered cards when a model filter changes", async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({
        items: [
          {
            slug: "fundas-galaxy-s24",
            name: "Funda Galaxy S24",
            priceFrom: 4000,
            hasPriceRange: false,
            heroImageUrl: null,
            heroImageAlt: "Funda Galaxy S24",
          },
        ],
        page: 1,
        limit: 12,
        total: 1,
        totalPages: 1,
        filters: INITIAL_FILTERS,
        applied: { q: null, model: "Galaxy S24", color: null },
      }),
    );

    render(
      <CatalogFilters
        initialItems={INITIAL_ITEMS}
        initialFilters={INITIAL_FILTERS}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Galaxy S24" }));

    await waitFor(() => {
      expect(screen.getByText("Funda Galaxy S24")).toBeInTheDocument();
    });
    expect(screen.queryByText("Funda iPhone 15")).not.toBeInTheDocument();

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [requestUrl] = fetchSpy.mock.calls[0];
    expect(String(requestUrl)).toContain("/api/catalog");
    expect(String(requestUrl)).toContain("model=Galaxy+S24");
  });

  it("updates the URL via history.replaceState instead of a full navigation", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({
        items: [],
        page: 1,
        limit: 12,
        total: 0,
        totalPages: 1,
        filters: INITIAL_FILTERS,
        applied: { q: null, model: "Galaxy S24", color: null },
      }),
    );
    const replaceStateSpy = vi.spyOn(window.history, "replaceState");

    render(
      <CatalogFilters
        initialItems={INITIAL_ITEMS}
        initialFilters={INITIAL_FILTERS}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Galaxy S24" }));

    await waitFor(() => {
      expect(replaceStateSpy).toHaveBeenCalled();
    });
    const [, , urlArg] = replaceStateSpy.mock.calls.at(-1)!;
    expect(String(urlArg)).toContain("model=Galaxy+S24");
  });

  it("renders the no-results empty state when a search matches nothing", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({
        items: [],
        page: 1,
        limit: 12,
        total: 0,
        totalPages: 1,
        filters: INITIAL_FILTERS,
        applied: { q: null, model: "Galaxy S24", color: null },
      }),
    );

    render(
      <CatalogFilters
        initialItems={INITIAL_ITEMS}
        initialFilters={INITIAL_FILTERS}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Galaxy S24" }));

    await waitFor(() => {
      expect(
        screen.getByTestId("catalog-empty-state-no-results"),
      ).toBeInTheDocument();
    });
  });
});
