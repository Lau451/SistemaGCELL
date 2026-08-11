import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

/**
 * `/admin` — landing page for the authenticated admin area. Purely
 * structural (design.md's File Changes: "Landing"); the single spec
 * requirement it serves is being the default redirect target after
 * login/already-authenticated-login-visit (`admin-authentication`
 * spec), so the one behavioral assertion worth making is that it links
 * onward to the one proof page this change actually ships.
 */

async function importPage() {
  const mod = await import("./page");
  return mod.default;
}

describe("AdminLandingPage", () => {
  it("links to the products proof page", async () => {
    const AdminLandingPage = await importPage();
    render(<AdminLandingPage />);

    expect(screen.getByRole("link", { name: /products/i })).toHaveAttribute(
      "href",
      "/admin/products",
    );
  });
});
