import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CatalogEmptyState } from "./catalog-empty-state";

describe("CatalogEmptyState", () => {
  it("renders the empty-catalog variant with a distinct testid and status role", () => {
    render(<CatalogEmptyState variant="empty-catalog" />);

    const status = screen.getByTestId("catalog-empty-state-empty-catalog");
    expect(status).toHaveAttribute("role", "status");
    expect(status).toHaveTextContent(/catálogo/i);
  });

  it("renders the no-results variant with a distinct testid, status role, and a clear-filters action", () => {
    render(<CatalogEmptyState variant="no-results" />);

    const status = screen.getByTestId("catalog-empty-state-no-results");
    expect(status).toHaveAttribute("role", "status");
    expect(screen.getByRole("link", { name: /limpiar filtros/i })).toBeInTheDocument();
  });

  it("renders the error variant with a distinct testid, status role, and a retry action", () => {
    render(<CatalogEmptyState variant="error" />);

    const status = screen.getByTestId("catalog-empty-state-error");
    expect(status).toHaveAttribute("role", "status");
    expect(screen.getByRole("link", { name: /reintentar/i })).toBeInTheDocument();
  });

  it("renders genuinely distinct content across all three variants", () => {
    const { unmount: unmountEmpty } = render(<CatalogEmptyState variant="empty-catalog" />);
    const emptyText = screen.getByTestId("catalog-empty-state-empty-catalog").textContent;
    unmountEmpty();

    const { unmount: unmountNoResults } = render(<CatalogEmptyState variant="no-results" />);
    const noResultsText = screen.getByTestId("catalog-empty-state-no-results").textContent;
    unmountNoResults();

    render(<CatalogEmptyState variant="error" />);
    const errorText = screen.getByTestId("catalog-empty-state-error").textContent;

    expect(new Set([emptyText, noResultsText, errorText]).size).toBe(3);
  });
});
