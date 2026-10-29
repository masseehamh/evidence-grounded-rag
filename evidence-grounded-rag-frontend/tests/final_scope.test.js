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
