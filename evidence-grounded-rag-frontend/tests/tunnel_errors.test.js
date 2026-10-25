// Connection errors when the configured backend is a live Colab/ngrok tunnel that went away.
import test from "node:test";
import assert from "node:assert/strict";

process.env.VITE_API_BASE_URL = "https://example.ngrok-free.dev";
const api = await import("../src/api.js");

test("the backend URL is treated as configured", () => {
  assert.equal(api.isApiConfigured, true);
  assert.equal(api.API_BASE_URL, "https://example.ngrok-free.dev");
});

test("a network failure explains the tunnel may be offline", async () => {
  globalThis.fetch = async () => { throw new TypeError("fetch failed"); };
  await assert.rejects(() => api.askBackend({ question: "q", mode: "manual", evidence: "e" }),
    (err) => /Could not reach the backend/.test(err.message) && /Colab\/ngrok tunnel/.test(err.message));
});

test("an HTML 404 from an expired tunnel explains how to recover", async () => {
  globalThis.fetch = async () => ({
    ok: false,
    status: 404,
    text: async () => "<!DOCTYPE html><html><body>ERR_NGROK_3200 tunnel not found</body></html>",
  });
  await assert.rejects(() => api.checkHealth(),
    (err) => /HTTP 404/.test(err.message) && /restart it/.test(err.message) && !/<!DOCTYPE/.test(err.message));
});
