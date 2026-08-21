import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

/**
 * `VariantSwitcher` — server-rendered link row on the product detail page
 * (design.md DD3/D14). Covers: renders nothing for a single-variant
 * product; one link per variant for 2+ variants; `aria-current="page"` on
 * the active variant's link; hrefs preserve any active `since`/`until`
 * (D12); the offset in a preserved date survives percent-encoded, not as
 * a literal space.
 *
 * @see design.md "DD3", "Interfaces / Contracts"
 */

async function importSwitcher() {
  const mod = await import("./variant-switcher");
  return mod.VariantSwitcher;
}

describe("VariantSwitcher", () => {
  it("renders nothing for a single-variant product", async () => {
    const VariantSwitcher = await importSwitcher();
    const { container } = render(
      <VariantSwitcher
        productId="p1"
        variants={[{ id: "v1", color: "negro" }]}
        activeVariantId="v1"
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("renders one link per variant for a multi-variant product", async () => {
    const VariantSwitcher = await importSwitcher();
    render(
      <VariantSwitcher
        productId="p1"
        variants={[
          { id: "v1", color: "negro" },
          { id: "v2", color: "azul" },
          { id: "v3", color: "rojo" },
        ]}
        activeVariantId="v1"
      />,
    );

    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(3);
    expect(screen.getByRole("link", { name: "negro" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "azul" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "rojo" })).toBeInTheDocument();
  });

  it("marks the active variant's link with aria-current=page and no other link", async () => {
    const VariantSwitcher = await importSwitcher();
    render(
      <VariantSwitcher
        productId="p1"
        variants={[
          { id: "v1", color: "negro" },
          { id: "v2", color: "azul" },
        ]}
        activeVariantId="v2"
      />,
    );

    expect(screen.getByRole("link", { name: "azul" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      screen.getByRole("link", { name: "negro" }),
    ).not.toHaveAttribute("aria-current");
  });

  it("each link's href points at ?variant=<id> for that specific variant", async () => {
    const VariantSwitcher = await importSwitcher();
    render(
      <VariantSwitcher
        productId="p1"
        variants={[
          { id: "v1", color: "negro" },
          { id: "v2", color: "azul" },
        ]}
        activeVariantId="v1"
      />,
    );

    const azulHref = screen.getByRole("link", { name: "azul" }).getAttribute("href");
    expect(azulHref).not.toBeNull();
    const query = new URLSearchParams(azulHref!.split("?")[1]);
    expect(query.get("variant")).toBe("v2");
  });

  it("preserves active since/until on every link, offset percent-encoded not a space", async () => {
    const VariantSwitcher = await importSwitcher();
    render(
      <VariantSwitcher
        productId="p1"
        variants={[
          { id: "v1", color: "negro" },
          { id: "v2", color: "azul" },
        ]}
        activeVariantId="v1"
        since="2026-08-01T00:00:00.000000-03:00"
        until="2026-08-15T23:59:59.999999-03:00"
      />,
    );

    const azulHref = screen
      .getByRole("link", { name: "azul" })
      .getAttribute("href")!;

    expect(azulHref).not.toContain(" ");
    const query = new URLSearchParams(azulHref.split("?")[1]);
    expect(query.get("since")).toBe("2026-08-01T00:00:00.000000-03:00");
    expect(query.get("until")).toBe("2026-08-15T23:59:59.999999-03:00");
  });
});
