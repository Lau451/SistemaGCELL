import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `ImageManager` — client component rendered on the product detail page,
 * the sole UI surface for the upload/delete/reorder Server Actions.
 * `./actions` and `next/navigation` are mocked following
 * `product-form.test.tsx`'s exact convention; `@/lib/supabase/env` is
 * mocked following `api/catalog/route.test.ts`'s convention so thumbnail
 * `src` resolves without a real `NEXT_PUBLIC_SUPABASE_URL`.
 */

const UPLOAD_ACTION = vi.fn();
const DELETE_ACTION = vi.fn();
const REORDER_ACTION = vi.fn();
const UPDATE_ALT_TEXT_ACTION = vi.fn();
const GENERATE_ALT_TEXT_ACTION = vi.fn();
const ROUTER_REFRESH = vi.fn();

vi.mock("./actions", () => ({
  uploadProductImageAction: (...args: unknown[]) => UPLOAD_ACTION(...args),
  deleteProductImageAction: (...args: unknown[]) => DELETE_ACTION(...args),
  reorderProductImagesAction: (...args: unknown[]) => REORDER_ACTION(...args),
  updateProductImageAltTextAction: (...args: unknown[]) =>
    UPDATE_ALT_TEXT_ACTION(...args),
  generateImageAltTextAction: (...args: unknown[]) =>
    GENERATE_ALT_TEXT_ACTION(...args),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: ROUTER_REFRESH }),
}));

vi.mock("@/lib/supabase/env", () => ({
  getCatalogSupabaseEnv: () => ({
    url: "http://127.0.0.1:54321",
    anonKey: "anon-key",
  }),
}));

async function importImageManager() {
  const mod = await import("./image-manager");
  return mod.ImageManager;
}

const VARIANTS = [
  { id: "v1", color: "negro" },
  { id: "v2", color: "rojo" },
];

const IMAGES = [
  {
    id: "img1",
    product_id: "p1",
    variant_id: null,
    storage_path: "funda-iphone-16/hero-abc123.webp",
    alt_text: "Hero shot",
    sort_order: 0,
  },
  {
    id: "img2",
    product_id: "p1",
    variant_id: "v1",
    storage_path: "funda-iphone-16/negro-def456.webp",
    alt_text: null,
    sort_order: 1,
  },
];

describe("ImageManager", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("renders a thumbnail for each initial image with its assignment label", async () => {
    const ImageManager = await importImageManager();

    const { container } = render(
      <ImageManager
        productId="p1"
        variants={VARIANTS}
        initialImages={IMAGES}
      />,
    );

    expect(screen.getByText("Portada")).toBeInTheDocument();
    // "negro" also appears as a <select> option (assign-to dropdown), so
    // scope this to the thumbnail's assignment label span specifically.
    expect(
      screen.getByText("negro", { selector: "span.font-medium" }),
    ).toBeInTheDocument();
    // A raw querySelector, not `getAllByRole("img")`: the second image's
    // `alt_text` is null -> `alt=""`, which ARIA treats as presentational
    // (removed from the "img" role), so a role query alone would miss it.
    expect(container.querySelectorAll("img")).toHaveLength(2);
    expect(screen.getByAltText("Hero shot")).toHaveAttribute(
      "src",
      "http://127.0.0.1:54321/storage/v1/object/public/product-photos/funda-iphone-16/hero-abc123.webp",
    );
  });

  it("renders the hero/variant assignment dropdown", async () => {
    const ImageManager = await importImageManager();

    render(
      <ImageManager productId="p1" variants={VARIANTS} initialImages={[]} />,
    );

    const select = screen.getByLabelText(/asignar a/i);
    expect(select).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: /portada \(sin variante\)/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "negro" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "rojo" })).toBeInTheDocument();
  });

  it("submits uploadProductImageAction bound to the productId on form submit", async () => {
    UPLOAD_ACTION.mockResolvedValue({ error: null });
    const user = userEvent.setup();
    const ImageManager = await importImageManager();

    render(
      <ImageManager productId="p1" variants={VARIANTS} initialImages={[]} />,
    );

    const file = new File(["fake-bytes"], "photo.webp", {
      type: "image/webp",
    });
    await user.upload(screen.getByLabelText(/archivo de imagen/i), file);
    await user.selectOptions(screen.getByLabelText(/asignar a/i), "v1");
    await user.type(screen.getByLabelText(/texto alternativo/i), "A red case");
    await user.click(screen.getByRole("button", { name: /subir imagen/i }));

    await waitFor(() => {
      expect(UPLOAD_ACTION).toHaveBeenCalledTimes(1);
    });
    const [productId, , formData] = UPLOAD_ACTION.mock.calls[0] as [
      string,
      unknown,
      FormData,
    ];
    expect(productId).toBe("p1");
    // jsdom's `new FormData(form)` does not faithfully round-trip a
    // programmatically-assigned `<input type="file">` value (a documented
    // jsdom/testing-library gap — see e.g.
    // testing-library/user-event#1075) — `File` relay-without-buffering is
    // already proven end-to-end against the real action function in
    // `actions.test.ts` (6.3's exact-instance-identity assertion). This
    // test proves the COMPONENT wiring instead: the action is bound to
    // this productId and the sibling text/select fields submit correctly.
    expect(formData.get("file")).toBeInstanceOf(File);
    expect(formData.get("variant-id")).toBe("v1");
    expect(formData.get("alt-text")).toBe("A red case");
  });

  it("refreshes the router after a successful upload", async () => {
    UPLOAD_ACTION.mockResolvedValue({ error: null });
    const user = userEvent.setup();
    const ImageManager = await importImageManager();

    render(
      <ImageManager productId="p1" variants={VARIANTS} initialImages={[]} />,
    );

    const file = new File(["fake-bytes"], "photo.webp", {
      type: "image/webp",
    });
    await user.upload(screen.getByLabelText(/archivo de imagen/i), file);
    await user.click(screen.getByRole("button", { name: /subir imagen/i }));

    await waitFor(() => {
      expect(ROUTER_REFRESH).toHaveBeenCalledTimes(1);
    });
  });

  it("surfaces an upload error via role=alert", async () => {
    UPLOAD_ACTION.mockResolvedValue({ error: "Unsupported image format" });
    const user = userEvent.setup();
    const ImageManager = await importImageManager();

    render(
      <ImageManager productId="p1" variants={VARIANTS} initialImages={[]} />,
    );

    const file = new File(["fake-bytes"], "photo.txt", {
      type: "text/plain",
    });
    await user.upload(screen.getByLabelText(/archivo de imagen/i), file);
    await user.click(screen.getByRole("button", { name: /subir imagen/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Unsupported image format",
      );
    });
    expect(ROUTER_REFRESH).not.toHaveBeenCalled();
  });

  it("deletes an image with the correct product-id/image-id", async () => {
    DELETE_ACTION.mockResolvedValue(undefined);
    const user = userEvent.setup();
    const ImageManager = await importImageManager();

    render(
      <ImageManager
        productId="p1"
        variants={VARIANTS}
        initialImages={IMAGES}
      />,
    );

    const [firstDelete] = screen.getAllByRole("button", { name: /eliminar/i });
    await user.click(firstDelete);

    await waitFor(() => {
      expect(DELETE_ACTION).toHaveBeenCalledTimes(1);
    });
    const [formData] = DELETE_ACTION.mock.calls[0] as [FormData];
    expect(formData.get("product-id")).toBe("p1");
    expect(formData.get("image-id")).toBe("img1");

    await waitFor(() => {
      expect(ROUTER_REFRESH).toHaveBeenCalledTimes(1);
    });
  });

  it("disables Up on the first image and Down on the last image", async () => {
    const ImageManager = await importImageManager();

    render(
      <ImageManager
        productId="p1"
        variants={VARIANTS}
        initialImages={IMAGES}
      />,
    );

    const upButtons = screen.getAllByRole("button", { name: /^subir$/i });
    const downButtons = screen.getAllByRole("button", { name: /^bajar$/i });

    expect(upButtons[0]).toBeDisabled();
    expect(downButtons[0]).not.toBeDisabled();
    expect(upButtons[1]).not.toBeDisabled();
    expect(downButtons[1]).toBeDisabled();
  });

  it("renders alt text as an editable field on an already-uploaded image, pre-filled with its current value", async () => {
    const ImageManager = await importImageManager();

    render(
      <ImageManager
        productId="p1"
        variants={VARIANTS}
        initialImages={IMAGES}
      />,
    );

    const altTextInputs = screen.getAllByLabelText(/^texto alternativo$/i);
    expect(altTextInputs).toHaveLength(2);
    expect(altTextInputs[0]).toHaveValue("Hero shot");
    expect(altTextInputs[1]).toHaveValue("");
  });

  it("saves an edited alt text via updateProductImageAltTextAction and refreshes the router", async () => {
    UPDATE_ALT_TEXT_ACTION.mockResolvedValue({ error: null });
    const user = userEvent.setup();
    const ImageManager = await importImageManager();

    render(
      <ImageManager
        productId="p1"
        variants={VARIANTS}
        initialImages={IMAGES}
      />,
    );

    const [firstAltTextInput] = screen.getAllByLabelText(/^texto alternativo$/i);
    await user.clear(firstAltTextInput);
    await user.type(firstAltTextInput, "Updated alt text");
    const [firstSaveButton] = screen.getAllByRole("button", {
      name: /guardar texto alternativo/i,
    });
    await user.click(firstSaveButton);

    await waitFor(() => {
      expect(UPDATE_ALT_TEXT_ACTION).toHaveBeenCalledTimes(1);
    });
    const [formData] = UPDATE_ALT_TEXT_ACTION.mock.calls[0] as [FormData];
    expect(formData.get("product-id")).toBe("p1");
    expect(formData.get("image-id")).toBe("img1");
    expect(formData.get("alt-text")).toBe("Updated alt text");

    await waitFor(() => {
      expect(ROUTER_REFRESH).toHaveBeenCalledTimes(1);
    });
  });

  it("surfaces an alt-text save error via role=alert", async () => {
    UPDATE_ALT_TEXT_ACTION.mockResolvedValue({ error: "Image not found" });
    const user = userEvent.setup();
    const ImageManager = await importImageManager();

    render(
      <ImageManager
        productId="p1"
        variants={VARIANTS}
        initialImages={IMAGES}
      />,
    );

    const [firstSaveButton] = screen.getAllByRole("button", {
      name: /guardar texto alternativo/i,
    });
    await user.click(firstSaveButton);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Image not found");
    });
    expect(ROUTER_REFRESH).not.toHaveBeenCalled();
  });

  it("Generate alt text button calls generateImageAltTextAction and prefills the alt-text input without submitting", async () => {
    GENERATE_ALT_TEXT_ACTION.mockResolvedValue({
      alt_text: "Funda negra brillante para telefono",
      error: null,
    });
    const user = userEvent.setup();
    const ImageManager = await importImageManager();

    render(
      <ImageManager
        productId="p1"
        variants={VARIANTS}
        initialImages={IMAGES}
      />,
    );

    const [firstGenerateButton] = screen.getAllByRole("button", {
      name: /generar texto alternativo/i,
    });
    await user.click(firstGenerateButton);

    await waitFor(() => {
      expect(GENERATE_ALT_TEXT_ACTION).toHaveBeenCalledWith("p1", "img1");
    });
    await waitFor(() => {
      const [firstAltTextInput] = screen.getAllByLabelText(/^texto alternativo$/i);
      expect(firstAltTextInput).toHaveValue("Funda negra brillante para telefono");
    });
    expect(UPDATE_ALT_TEXT_ACTION).not.toHaveBeenCalled();
    expect(ROUTER_REFRESH).not.toHaveBeenCalled();
  });

  it("surfaces a Generate alt text failure via role=alert without refreshing", async () => {
    GENERATE_ALT_TEXT_ACTION.mockResolvedValue({
      alt_text: null,
      error: "gemini_unavailable",
    });
    const user = userEvent.setup();
    const ImageManager = await importImageManager();

    render(
      <ImageManager
        productId="p1"
        variants={VARIANTS}
        initialImages={IMAGES}
      />,
    );

    const [firstGenerateButton] = screen.getAllByRole("button", {
      name: /generar texto alternativo/i,
    });
    await user.click(firstGenerateButton);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("gemini_unavailable");
    });
    expect(ROUTER_REFRESH).not.toHaveBeenCalled();
  });

  it("moves an image down and calls reorderProductImagesAction with the new order", async () => {
    REORDER_ACTION.mockResolvedValue({ error: null });
    const user = userEvent.setup();
    const ImageManager = await importImageManager();

    render(
      <ImageManager
        productId="p1"
        variants={VARIANTS}
        initialImages={IMAGES}
      />,
    );

    const downButtons = screen.getAllByRole("button", { name: /^bajar$/i });
    await user.click(downButtons[0]);

    await waitFor(() => {
      expect(REORDER_ACTION).toHaveBeenCalledTimes(1);
    });
    expect(REORDER_ACTION).toHaveBeenCalledWith("p1", ["img2", "img1"]);

    await waitFor(() => {
      expect(ROUTER_REFRESH).toHaveBeenCalledTimes(1);
    });
  });
});
