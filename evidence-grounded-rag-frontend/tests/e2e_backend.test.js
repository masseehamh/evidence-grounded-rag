// End-to-end: the frontend's own api.js against a RUNNING backend.
// Skipped unless E2E_API_URL is set (see ../../backend-tests/README.md).
import test from "node:test";
import assert from "node:assert/strict";

const BASE = process.env.E2E_API_URL;
const skip = BASE ? false : "set E2E_API_URL to run (needs the test backend running)";
process.env.VITE_API_BASE_URL = BASE || "";
const api = await import("../src/api.js");

const EVIDENCE = "In 1905, sometimes described as his annus mirabilis (miracle year), he published four groundbreaking papers.";
const QUESTION = "What year is described as Einstein's annus mirabilis (miracle year)?";

async function setAnswer(answer) {
  await fetch(`${BASE}/__set_answer`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answer }) });
}
async function ask(question, evidence) {
  return api.normalizeResult(await api.askBackend(api.buildAskPayload({ mode: "manual", question, evidence })));
}

test("health check", { skip }, async () => { assert.equal((await api.checkHealth()).status, "ok"); });

test("Einstein: manually pasted evidence yields SUPPORTED 1905", { skip }, async () => {
  await setAnswer("1905");
  const r = await ask(QUESTION, EVIDENCE);
  assert.equal(r.claims[0].status, "SUPPORTED");
  assert.equal(r.corrected_answer, "1905");
  assert.equal(r.claims[0].consistency.status, "PASS");
  // The stand-in NLI judge the rebuilt question+answer statement and says "entailment",
  // so a supported claim here carries the NLI score as its confidence.
  assert.equal(r.claims[0].nli_label, "entailment");
  assert.ok(r.claims[0].confidence > 0, "the NLI score is carried as the overall confidence");
  assert.equal(r.claims[0].support_basis, "nli_entailment");
  assert.equal(r.verification_status, "FULLY SUPPORTED");
});

test("unsupported question is NOT_ENOUGH_EVIDENCE and the answer is withheld", { skip }, async () => {
  await setAnswer("1905");
  const r = await ask("What year did Einstein win the Nobel Prize?", EVIDENCE);
  assert.equal(r.claims[0].status, "NOT_ENOUGH_EVIDENCE");
  assert.match(r.corrected_answer, /not sufficient/);
});

test("contradicted answer is CONTRADICTED and corrected from the evidence", { skip }, async () => {
  await setAnswer("1906");
  const r = await ask(QUESTION, EVIDENCE);
  assert.equal(r.claims[0].status, "CONTRADICTED");
  assert.doesNotMatch(r.corrected_answer, /1906/);
  assert.match(r.corrected_answer, /1905/);
});

test("empty evidence is rejected with a readable message", { skip }, async () => {
  await assert.rejects(() => api.askBackend({ question: QUESTION, mode: "manual", evidence: "" }), /evidence/i);
});

// ------------------------------------------------- the second supported workflow
test("document workflow: an uploaded document containing the answer works", { skip }, async () => {
  await setAnswer("1905");
  const doc = "Albert Einstein was a physicist who was born in Ulm.\n\n" + EVIDENCE;
  const uploaded = await api.uploadDocument(new Blob([doc], { type: "text/plain" }), "einstein.txt");
  assert.ok(uploaded.document_id, "the upload returns a document id");
  const r = api.normalizeResult(await api.askBackend(
    api.buildAskPayload({ mode: "document", question: QUESTION, documentId: uploaded.document_id })));
  assert.equal(r.claims[0].status, "SUPPORTED");
  assert.equal(r.corrected_answer, "1905");
  assert.equal(r.corrected_status, "SUPPORTED");
  assert.equal(r.sources[0].title, "einstein.txt");
  assert.match(r.sources[0].passage, /1905/, "the source passage is preserved");
});

test("an irrelevant document does not support the answer", { skip }, async () => {
  await setAnswer("1905");
  const doc = "Photosynthesis is the process plants use to convert sunlight into chemical energy.";
  const uploaded = await api.uploadDocument(new Blob([doc], { type: "text/plain" }), "plants.txt");
  const r = api.normalizeResult(await api.askBackend(
    api.buildAskPayload({ mode: "document", question: QUESTION, documentId: uploaded.document_id })));
  assert.equal(r.verification_status, "NOT ENOUGH EVIDENCE");
  assert.match(r.corrected_answer, /not sufficient/i);
  assert.equal(r.corrected_status, "NOT_ENOUGH_EVIDENCE");
});

test("bad uploads are rejected by the backend with readable errors", { skip }, async () => {
  await assert.rejects(
    () => api.uploadDocument(new Blob(["%PDF-1.4"], { type: "application/pdf" }), "x.pdf"),
    /txt/i);
  await assert.rejects(
    () => api.uploadDocument(new Blob(["   \n  "], { type: "text/plain" }), "empty.txt"),
    /empty/i);
  await assert.rejects(
    () => api.uploadDocument(new Blob(["a".repeat(2_000_001)], { type: "text/plain" }), "big.txt"),
    /too large/i);
});
