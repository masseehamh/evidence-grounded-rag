// Illustrative UI-only data. Never presented as output from the real model.
export const demoResult = {
  verification_status: "PARTIALLY_VERIFIED",
  original_answer: "The sample evidence says the prototype was tested with 120 examples. It achieved 91% accuracy and reduced hallucinations by 40% in every setting.",
  corrected_answer: "The sample evidence says the prototype was tested with 120 examples and achieved 91% accuracy. The evidence does not establish that hallucinations were reduced by 40% in every setting.",
  claims: [
    {
      claim: "The prototype was tested with 120 examples.",
      status: "SUPPORTED",
      evidence: "Sample report: “The prototype was evaluated on a test set containing 120 examples.”",
      nli_label: "entailment",
      confidence: 0.97,
      consistency: { status: "PASS", details: "The number 120 matches the evidence." }
    },
    {
      claim: "It achieved 91% accuracy.",
      status: "SUPPORTED",
      evidence: "Sample report: “Measured accuracy on the held-out set was 91%.”",
      nli_label: "entailment",
      confidence: 0.93,
      consistency: { status: "PASS", details: "The percentage 91% matches the evidence." }
    },
    {
      claim: "It reduced hallucinations by 40% in every setting.",
      status: "NOT_ENOUGH_EVIDENCE",
      evidence: "The sample evidence contains no measurement of a 40% reduction or a comparison across every setting.",
      nli_label: "neutral",
      confidence: 0.89,
      consistency: { status: "NOT_CHECKED", details: "No matching numerical result was found." }
    }
  ],
  removed_claims: [
    "“Reduced hallucinations by 40% in every setting” — omitted from the corrected answer because the supplied evidence does not establish it."
  ],
  sources: []
};
