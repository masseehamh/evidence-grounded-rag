// Final-demo workflow checks: upload validation, request timeouts, and the UI
// guards that keep the page honest (no fake badges, no misleading file picker).
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

process.env.VITE_API_BASE_URL = "http://backend.test";
const api = await import("../src/api.js");
const appSource = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");

// ------------------------------------------------- upload validation (client side)
test("a valid .txt file inside the size limit passes validation", () => {
  assert.equal(api.validateUploadFile({ name: "notes.txt", size: 1200 }), null);
});

test("unsupported file types are rejected with an actionable message", () => {
  const message = api.validateUploadFile({ name: "thesis.pdf", size: 5000 });
  assert.match(message, /thesis\.pdf/);
  assert.match(message, /\.txt/);
});

test("an empty document is rejected with a clear message", () => {
  assert.match(api.validateUploadFile({ name: "empty.txt", size: 0 }), /empty/i);
  assert.match(api.validateUploadFile({ name: "no-size.txt" }), /empty/i);
});

test("an oversized document names the limit and suggests an alternative", () => {
  const message = api.validateUploadFile({ name: "big.txt", size: 3_000_000 });
  assert.match(message, /too large/i);
  assert.match(message, /2 MB/);
  assert.match(message, /manual evidence/i);
});

test("a missing file asks the user to choose one", () => {
  assert.match(api.validateUploadFile(null), /choose/i);
  assert.match(api.validateUploadFile(undefined), /choose/i);
});

// --------------------------------------------------------------------- timeouts
test("a timed-out request becomes a readable message, not a hang", async () => {
  globalThis.fetch = async () => { throw new DOMException("The operation timed out.", "TimeoutError"); };
  await assert.rejects(() => api.checkHealth(), /did not answer in time/);
});

test("a genuine network failure still reports an unreachable backend", async () => {
  globalThis.fetch = async () => { throw new TypeError("fetch failed"); };
  await assert.rejects(() => api.checkHealth(), /Could not reach the backend/);
});

test("timeouts are configurable per call and default to the ask timeout", async () => {
  let seen;
  globalThis.fetch = async (url, options) => {
    seen = options;
    return { ok: true, json: async () => ({ status: "ok" }) };
  };
  await api.checkHealth();
  assert.ok(seen.signal instanceof AbortSignal, "a timeout signal is attached");
  await api.uploadDocument(new Blob(["x"], { type: "text/plain" }), "x.txt");
  assert.ok(seen.signal instanceof AbortSignal);
  await api.askBackend({ question: "q", mode: "manual", evidence: "e" });
  assert.ok(seen.signal instanceof AbortSignal);
});

// ------------------------------------------------------------- honest UI guards
test("the file picker only offers the supported .txt format", () => {
  assert.match(appSource, /accept="\.txt,text\/plain"/);
  assert.doesNotMatch(appSource, /\.pdf/);
});

test("the upload success indicator is not a green SUPPORTED status pill", () => {
  assert.match(appSource, /className="upload-ready"/);
  assert.doesNotMatch(appSource, /\{documentId && <StatusPill status="SUPPORTED" \/>}/);
});

test("the results page explains the insufficient-evidence case", () => {
  assert.match(appSource, /insufficient-note/);
  assert.match(appSource, /does not contain enough information/);
});

test("the submit button shows progress while a request is running", () => {
  assert.match(appSource, /Uploading document…/);
  assert.match(appSource, /Processing…/);
});

test("an empty claim list in the insufficient case speaks to the user, not the developer", () => {
  // The document relevance gate legitimately returns zero claims; the page must
  // explain the withheld answer instead of showing the internal `claims` hint.
  assert.match(appSource, /\{insufficient\s*\n?\s*\? "No claims were extracted/);
  assert.match(appSource, /the answer was withheld/);
});
