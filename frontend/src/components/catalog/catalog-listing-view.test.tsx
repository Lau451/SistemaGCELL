import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CatalogListingView } from "./catalog-listing-view";

const CARD_A = {
  slug: "fundas-iphone-15",
  name: "Funda iPhone 15",
  priceFrom: 12990,
  hasPriceRange: true,
  imageUrl: null,
  imageAlt: "Funda iPhone 15",
};

const CARD_B = {
  slug: "fundas-galaxy-s24",
  name: "Funda Galaxy S24",
  priceFrom: 14990,
  hasPriceRange: false,
  imageUrl: null,
  imageAlt: "Funda Galaxy S24",
};

describe("CatalogListingView", () => {
  it("renders a grid with one card per product when products exist", () => {
    render(<CatalogListingView products={[CARD_A, CARD_B]} />);

    expect(screen.getByTestId("catalog-listing-grid")).toBeInTheDocument();
    expect(screen.getByText("Funda iPhone 15")).toBeInTheDocument();
    expect(screen.getByText("Funda Galaxy S24")).toBeInTheDocument();
  });

  it("renders the empty-catalog state, not a grid, when products is empty and no override is given", () => {
    render(<CatalogListingView products={[]} />);

    expect(screen.getByTestId("catalog-empty-state-empty-catalog")).toBeInTheDocument();
    expect(screen.queryByTestId("catalog-listing-grid")).not.toBeInTheDocument();
  });

  it("renders the explicit error state even when products is non-empty", () => {
    render(<CatalogListingView products={[CARD_A]} emptyStateVariant="error" />);

    expect(screen.getByTestId("catalog-empty-state-error")).toBeInTheDocument();
    expect(screen.queryByTestId("catalog-listing-grid")).not.toBeInTheDocument();
  });

  it("renders the no-results state when explicitly requested", () => {
    render(<CatalogListingView products={[]} emptyStateVariant="no-results" />);

    expect(screen.getByTestId("catalog-empty-state-no-results")).toBeInTheDocument();
  });
});
