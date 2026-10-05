import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

beforeEach(() => {
  vi.resetModules();
  vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000/api/v1/");
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});
describe("API transport", () => {
  it("rejects paths outside the API", async () => {
    const { apiGet } = await import("./client");
    await expect(apiGet("https://evil.example/")).rejects.toThrow("API path");
    await expect(apiGet("../admin/")).rejects.toThrow("API path");
  });
  it("preserves HTTP failures without exposing response bodies", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("secret", { status: 503 })),
    );
    const { apiGet } = await import("./client");
    await expect(apiGet("health/application/")).rejects.toMatchObject({
      status: 503,
      message: "API request failed (503)",
    });
  });
  it("requires explicit configuration", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "");
    const { apiGet } = await import("./client");
    await expect(apiGet("health/application/")).rejects.toThrow(
      "VITE_API_BASE_URL is required",
    );
  });
  it("returns successful JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({ status: "ok" })),
    );
    const { apiGet } = await import("./client");
    await expect(apiGet("health/application/")).resolves.toEqual({
      status: "ok",
    });
  });
});
