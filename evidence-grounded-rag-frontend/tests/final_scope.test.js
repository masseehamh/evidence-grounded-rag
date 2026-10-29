import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

process.env.VITE_API_BASE_URL = "http://backend.test";
const api = await import("../src/api.js");

const appSource = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
const RESULT = {
  verification_status: "NEEDS VERIFICATION",
  original_answer: "India",
  corrected_answer: "1921",
  claims: [{ claim: "India", status: "NOT_ENOUGH_EVIDENCE", evidence: "..." }],
  removed_claims: [{ claim: "India" }],
  sources: [],
};

test("the workspace offers website search, manual evidence and document upload", () => {
  assert.match(appSource, /title="Website search"/);
  assert.match(appSource, /selectMode\("web"\)/);
  assert.match(appSource, /title="Manual evidence"/);
  assert.match(appSource, /title="Upload document"/);
  // Manual evidence is the default mode and must be visible without extra clicks.
  assert.match(appSource, /const \[mode, setMode\] = useState\("manual"\)/);
  assert.match(appSource, /const \[showAdvanced, setShowAdvanced\] = useState\(true\)/);
  assert.match(appSource, /mode === "web"/);
});

test("the corrected-answer badge is driven by corrected_status, not hard-coded", () => {
  assert.match(appSource, /StatusPill status=\{result\.corrected_status \|\| "UNCHECKED"\}/);
  assert.doesNotMatch(appSource, /corrected-card[\s\S]{0,400}StatusPill status="SUPPORTED"/);
});

test("corrected_status from the backend is normalized for the pill", () => {
  assert.equal(api.normalizeResult({ ...RESULT, corrected_status: "SUPPORTED" }).corrected_status, "SUPPORTED");
  assert.equal(api.normalizeResult({ ...RESULT, corrected_status: "NOT_ENOUGH_EVIDENCE" }).corrected_status,
    "NOT_ENOUGH_EVIDENCE");
  // an overall-style status still maps onto a claim-level pill
  assert.equal(api.normalizeResult({ ...RESULT, corrected_status: "CONTAINS HALLUCINATION" }).corrected_status,
    "CONTRADICTED");
  assert.equal(api.normalizeResult({ ...RESULT, corrected_status: "FULLY SUPPORTED" }).corrected_status,
    "SUPPORTED");
});

test("a backend that omits corrected_status never gets a fake SUPPORTED badge", () => {
  assert.equal(api.normalizeResult(RESULT).corrected_status, null);
});

test("the evidence behind a corrected answer is preserved for display", () => {
  const withEvidence = api.normalizeResult({
    ...RESULT,
    corrected_status: "SUPPORTED",
    corrected_evidence: "Assuming leadership of the Indian National Congress in 1921, Gandhi led nationwide campaigns.",
  });
  assert.match(withEvidence.corrected_evidence, /1921/);
  assert.equal(api.normalizeResult(RESULT).corrected_evidence, "");
});


test("mobile navigation has a visible menu control and closes through the drawer backdrop", () => {
  assert.match(appSource, /className="menu-button"/);
  assert.match(appSource, /aria-expanded=\{mobileNavOpen\}/);
  assert.match(appSource, /className="drawer-backdrop"/);
  assert.match(appSource, /setMobileNavOpen\(false\)/);
});

test("verification results explain the empty state and offer a start action", () => {
  assert.doesNotMatch(appSource, /disabled=\{!result\}/);
  assert.match(appSource, /Ask a question first/);
  assert.match(appSource, /Start a question/);
});

test("clear action is beside the question field, not in the page heading", () => {
  assert.match(appSource, /question-field-actions[\s\S]*?onClick=\{clearForm\}/);
  assert.doesNotMatch(appSource, /page-heading[\s\S]{0,500}onClick=\{clearForm\}/);
});

test("report omits unsupported confidence percentages and labels the actual verifier", () => {
  assert.doesNotMatch(appSource, /OVERALL CONFIDENCE/);
  assert.match(appSource, /Instruction-model verifier/);
  assert.match(appSource, /separately trained NLI classifier/);
  assert.match(appSource, /className="claim-details"/);
  assert.match(appSource, /className="source-details"/);
});


test("claim report shows verdict, decisive evidence, and the backend reason before technical details", () => {
  assert.match(appSource, /Decisive evidence/);
  assert.match(appSource, /Why this verdict/);
  assert.match(appSource, /claim\.reason \|\|/);
  assert.match(appSource, /Technical verification details/);
  assert.match(appSource, /NUMERIC CONSISTENCY CHECK/);
  assert.doesNotMatch(appSource, /OVERALL CONFIDENCE|\b\d+% confidence/i);
});

test("mobile navigation closes on Escape and responsive report content can wrap", () => {
  assert.match(appSource, /event\.key === "Escape"/);
});
