import { afterEach, describe, expect, it } from "vitest";
import { getBackendUrl } from "@/lib/admin/env";

const ORIGINAL_BACKEND_URL = process.env.BACKEND_URL;

afterEach(() => {
  process.env.BACKEND_URL = ORIGINAL_BACKEND_URL;
});

describe("getBackendUrl", () => {
  it("defaults to 127.0.0.1:8000 (not localhost) when BACKEND_URL is unset", () => {
    delete process.env.BACKEND_URL;

    expect(getBackendUrl()).toBe("http://127.0.0.1:8000");
  });

  it("returns the configured BACKEND_URL when set", () => {
    process.env.BACKEND_URL = "http://127.0.0.1:9000";

    expect(getBackendUrl()).toBe("http://127.0.0.1:9000");
  });
});
