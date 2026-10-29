import test from "node:test";
import assert from "node:assert/strict";

process.env.VITE_API_BASE_URL = "http://backend.test";
const api = await import("../src/api.js");

const QUESTION = "What year is described as Einstein's annus mirabilis (miracle year)?";
const EVIDENCE = "In 1905, sometimes described as his annus mirabilis (miracle year), he published four groundbreaking papers.";

test("manual mode sends question, mode and evidence (trimmed) to /api/ask", () => {
  const payload = api.buildAskPayload({ mode: "manual", question: `  ${QUESTION}  `, evidence: `\n${EVIDENCE}\n` });
  assert.deepEqual(payload, { question: QUESTION, mode: "manual", evidence: EVIDENCE });
});

test("manual and document modes carry their evidence inputs, while web mode needs no pasted evidence", () => {
  assert.deepEqual(api.buildAskPayload({ mode: "document", question: "q", documentId: "abc" }),
    { question: "q", mode: "document", document_id: "abc" });
  assert.deepEqual(api.buildAskPayload({ mode: "web", question: "q" }), { question: "q", mode: "web" });
});

test("askBackend POSTs JSON to the configured URL with the evidence intact", async () => {
  let seen;
  globalThis.fetch = async (url, options) => {
    seen = { url, options };
    return { ok: true, json: async () => ({}) };
  };
  await api.askBackend(api.buildAskPayload({ mode: "manual", question: QUESTION, evidence: EVIDENCE }));
  assert.equal(seen.url, "http://backend.test/api/ask");
  assert.equal(seen.options.method, "POST");
  assert.equal(seen.options.headers["Content-Type"], "application/json");
  assert.deepEqual(JSON.parse(seen.options.body), { question: QUESTION, mode: "manual", evidence: EVIDENCE });
});

test("a backend response for the Einstein case is displayed as SUPPORTED with a PASS check", () => {
  const result = api.normalizeResult({
    verification_status: "FULLY SUPPORTED",
    original_answer: "1905",
    corrected_answer: "1905",
    claims: [{
      claim: "1905", status: "SUPPORTED", evidence: EVIDENCE, nli_label: "entailment", confidence: 0.97,
      consistency: { status: "PASS", details: "Numbers: ok | Entities: ok" },
    }],
    removed_claims: [], sources: [],
  });
  assert.equal(result.claims[0].status, "SUPPORTED");
  assert.equal(result.claims[0].confidence, 97);
  assert.equal(result.claims[0].consistency.status, "PASS");
  assert.equal(result.corrected_answer, "1905");
});

test("backend errors reach the UI as readable messages", async () => {
  globalThis.fetch = async () => ({ ok: false, status: 400, text: async () => '{"detail":"Please provide evidence text."}' });
  await assert.rejects(() => api.askBackend({ question: "q", mode: "manual" }), /provide evidence/);
  globalThis.fetch = async () => { throw new TypeError("fetch failed"); };
  await assert.rejects(() => api.askBackend({ question: "q", mode: "manual" }), /Could not reach the backend/);
});

test("every request sends the ngrok browser-warning bypass header", async () => {
  let seen;
  globalThis.fetch = async (url, options) => {
    seen = { url, options };
    return { ok: true, json: async () => ({ status: "ok" }) };
  };
  assert.deepEqual(await api.checkHealth(), { status: "ok" });
  assert.equal(seen.options.headers["ngrok-skip-browser-warning"], "1");
  // The caller's own headers still win.
  await api.askBackend(api.buildAskPayload({ mode: "manual", question: "q", evidence: "e" }));
  assert.equal(seen.options.headers["Content-Type"], "application/json");
});

test("an HTML error page from an expired tunnel becomes a readable message", async () => {
  globalThis.fetch = async () => ({
    ok: false,
    status: 404,
    text: async () => "<!DOCTYPE html><html><body><h1>Tunnel not found</h1></body></html>",
  });
  await assert.rejects(() => api.askBackend({ question: "q", mode: "manual", evidence: "e" }), (err) =>
    /without a readable API error/.test(err.message) && !/<!DOCTYPE/.test(err.message));
});

test("a 200 HTML interstitial does not surface as broken JSON", async () => {
  globalThis.fetch = async () => ({
    ok: true,
    status: 200,
    json: async () => { throw new SyntaxError("Unexpected token < in JSON at position 0"); },
    text: async () => "<html><body>Click to continue</body></html>",
  });
  await assert.rejects(() => api.checkHealth(), /web page instead of JSON/);
});
