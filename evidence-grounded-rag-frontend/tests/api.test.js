import test from "node:test";
import assert from "node:assert/strict";
import { normalizeResult } from "../src/api.js";
import { demoResult } from "../src/demoData.js";

test("normalizes a basic backend result and claim statuses", () => {
  const result = normalizeResult({
    overall_status: "PARTIALLY_VERIFIED",
    generated_answer: "Original",
    final_answer: "Corrected",
    claims: [
      { text: "Claim A", label: "SUPPORTED", confidence: 0.91, evidence: "Evidence A" },
      { text: "Claim B", status: "CONTRADICTED", confidence: 88 },
      { text: "Claim C", status: "neutral" }
    ]
  });
  assert.equal(result.original_answer, "Original");
  assert.equal(result.corrected_answer, "Corrected");
  assert.equal(result.claims[0].status, "SUPPORTED");
  assert.equal(result.claims[0].confidence, 91);
  assert.equal(result.claims[1].confidence, 88);
  assert.equal(result.claims[2].status, "NOT_ENOUGH_EVIDENCE");
});

test("preserves verifier reasons and explanations for the results page", () => {
  const result = normalizeResult({
    claims: [{
      claim: "Incline push-ups help beginners build strength.",
      status: "SUPPORTED",
      evidence: "Incline push-ups are a progression.",
      reason: "The cited passage directly describes incline push-ups as a beginner progression."
    }]
  });
  assert.equal(
    result.claims[0].reason,
    "The cited passage directly describes incline push-ups as a beginner progression."
  );
});

test("handles missing optional fields without inventing data", () => {
  const result = normalizeResult({});
  assert.equal(result.original_answer, "");
  assert.equal(result.corrected_answer, "");
  assert.deepEqual(result.claims, []);
  assert.deepEqual(result.sources, []);
  assert.equal(result.verification_status, "STATUS_UNAVAILABLE");
});

test("rejects invalid top-level responses", () => {
  assert.throws(() => normalizeResult(null), /invalid/i);
});

test("demo results are normalized before display so fractions become percentages", () => {
  // demoResult ships confidence as 0-1 fractions; the UI shows Math.round(confidence)%,
  // so an un-normalized demo result renders a supported claim at "1%" instead of "97%".
  const result = normalizeResult(demoResult);
  assert.equal(result.verification_status, "PARTIALLY_VERIFIED");
  assert.equal(result.claims.length, 3);
  assert.equal(result.claims[0].status, "SUPPORTED");
  assert.equal(result.claims[0].confidence, 97);
  assert.equal(result.claims[1].status, "SUPPORTED");
  assert.equal(result.claims[1].confidence, 93);
  assert.equal(result.claims[2].status, "NOT_ENOUGH_EVIDENCE");
  assert.equal(result.claims[2].confidence, 89);
});

test("keeps NLI and overall confidence separate for deterministic short-answer support", () => {
  const result = normalizeResult({ claims: [{
    claim: "1905", status: "SUPPORTED", nli_label: "neutral", nli_confidence: 0.99,
    confidence: null, support_basis: "answer_span_in_evidence"
  }] });
  assert.equal(result.claims[0].nli_label, "neutral");
  assert.equal(result.claims[0].nli_confidence, 99);
  assert.equal(result.claims[0].confidence, null);
  assert.equal(result.claims[0].support_basis, "answer_span_in_evidence");
});

test("normalizes conversational backend responses for the dedicated conversation screen", () => {
  const result = normalizeResult({
    verification_status: "CONVERSATIONAL",
    verification_mode: "conversation",
    original_answer: "Nice try, Bruce!",
    corrected_answer: "Nice try, Bruce!",
    corrected_status: "NOT_APPLICABLE",
    claims: [],
    sources: [],
    message: "Evidence verification was not needed."
  });
  assert.equal(result.verification_mode, "conversation");
  assert.equal(result.verification_status, "CONVERSATIONAL");
  assert.equal(result.corrected_answer, "Nice try, Bruce!");
  assert.deepEqual(result.claims, []);
  assert.deepEqual(result.sources, []);
});
