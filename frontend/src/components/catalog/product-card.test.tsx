import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProductCard } from "./product-card";

describe("ProductCard", () => {
  it("renders a single price without a 'from' prefix when hasPriceRange is false", () => {
    render(
      <ProductCard
        slug="fundas-galaxy-s24"
        name="Funda Galaxy S24"
        priceFrom={14990}
        hasPriceRange={false}
        imageUrl="https://example.supabase.co/storage/v1/object/public/product-photos/fundas-galaxy-s24/negro.jpg"
        imageAlt="Funda Galaxy S24 negra"
      />,
    );

    const price = screen.getByTestId("product-card-price");
    expect(price).not.toHaveTextContent(/desde/i);
    expect(price.textContent).toMatch(/14\.990/);
  });

  it('renders the price prefixed with "Desde" when hasPriceRange is true', () => {
    render(
      <ProductCard
        slug="fundas-iphone-15"
        name="Funda iPhone 15"
        priceFrom={12990}
        hasPriceRange={true}
        imageUrl={null}
        imageAlt="Funda iPhone 15"
      />,
    );

    const price = screen.getByTestId("product-card-price");
    expect(price).toHaveTextContent(/desde/i);
    expect(price.textContent).toMatch(/12\.990/);
  });

  it("links to the product detail route by slug", () => {
    render(
      <ProductCard
        slug="fundas-iphone-15"
        name="Funda iPhone 15"
        priceFrom={12990}
        hasPriceRange={false}
        imageUrl={null}
        imageAlt="Funda iPhone 15"
      />,
    );

    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      "/product/fundas-iphone-15",
    );
  });

  it("renders the product name", () => {
    render(
      <ProductCard
        slug="fundas-iphone-15"
        name="Funda iPhone 15"
        priceFrom={12990}
        hasPriceRange={false}
        imageUrl={null}
        imageAlt="Funda iPhone 15"
      />,
    );

    expect(screen.getByText("Funda iPhone 15")).toBeInTheDocument();
  });

  it("renders a placeholder instead of a broken image when imageUrl is null", () => {
    render(
      <ProductCard
        slug="fundas-iphone-15"
        name="Funda iPhone 15"
        priceFrom={12990}
        hasPriceRange={false}
        imageUrl={null}
        imageAlt="Funda iPhone 15"
      />,
    );

    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("renders the shortDescription blurb when present", () => {
    render(
      <ProductCard
        slug="fundas-iphone-15"
        name="Funda iPhone 15"
        priceFrom={12990}
        hasPriceRange={false}
        imageUrl={null}
        imageAlt="Funda iPhone 15"
        shortDescription="Funda resistente y elegante."
      />,
    );

    expect(
      screen.getByText("Funda resistente y elegante."),
    ).toBeInTheDocument();
  });

  it("renders cleanly with no blurb placeholder when shortDescription is null", () => {
    render(
      <ProductCard
        slug="fundas-iphone-15"
        name="Funda iPhone 15"
        priceFrom={12990}
        hasPriceRange={false}
        imageUrl={null}
        imageAlt="Funda iPhone 15"
        shortDescription={null}
      />,
    );

    expect(
      screen.queryByTestId("product-card-blurb"),
    ).not.toBeInTheDocument();
  });
});
