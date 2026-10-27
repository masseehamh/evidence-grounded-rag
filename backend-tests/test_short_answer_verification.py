"""Tests for the 'explicit answer reported as NOT ENOUGH EVIDENCE' bug.

They run the notebook's own functions with stand-ins for MiniLM / DeBERTa / FLAN-T5
(see stubs.py). They check the notebook's decision logic, not real-model quality.
"""
import pytest
from conftest import script_generator

EINSTEIN_EVIDENCE = ("In 1905, sometimes described as his annus mirabilis (miracle year), "
                     "he published four groundbreaking papers.")
EINSTEIN_Q = "What year is described as Einstein's annus mirabilis (miracle year)?"
NOT_SUFFICIENT = "The available evidence is not sufficient to provide a verified answer."
EIFFEL = "The Eiffel Tower is a famous landmark located in Paris, France. It was completed in 1889."
KANSAS = ("Five people were infected and three died in the past year in Kansas "
          "from listeria that might be linked to Blue Bell Creameries products.")


def run(ns, question, evidence, generated, plain=""):
    script_generator(ns, generated, plain)
    return ns["run_full_rag_pipeline"](question, evidence, verbose=False)


# ---------------------------------------------------------------- the reported bug
class TestEinsteinExplicitAnswer:
    @pytest.mark.parametrize("generated", ["1905", "1905.", " 1905 "])
    def test_explicit_answer_is_supported(self, ns, generated):
        r = run(ns, EINSTEIN_Q, EINSTEIN_EVIDENCE, generated)
        claim = r["verification"]["claims"][0]
        assert claim["status"] == "SUPPORTED", claim
        assert r["verification"]["overall_status"] == "FULLY SUPPORTED"
        assert "1905" in r["correction"]["corrected_answer"]
        assert r["correction"]["corrected_answer"] != NOT_SUFFICIENT
        assert r["correction"]["correction_report"]["removed"] == 0

    def test_supported_answer_is_returned_untouched(self, ns):
        r = run(ns, EINSTEIN_Q, EINSTEIN_EVIDENCE, "1905")
        assert r["correction"]["corrected_answer"] == "1905"

    def test_full_sentence_answer_is_supported(self, ns_nli):
        r = run(ns_nli, EINSTEIN_Q, EINSTEIN_EVIDENCE, "The year 1905 is described as the annus mirabilis.")
        assert r["verification"]["claims"][0]["status"] == "SUPPORTED"

    def test_evidence_sentence_is_the_one_shown(self, ns):
        r = run(ns, EINSTEIN_Q, EINSTEIN_EVIDENCE, "1905")
        assert r["verification"]["claims"][0]["evidence"] == EINSTEIN_EVIDENCE

    def test_support_basis_is_reported(self, ns):
        c = run(ns, EINSTEIN_Q, EINSTEIN_EVIDENCE, "1905")["verification"]["claims"][0]
        assert c["support_basis"] in {"nli_entailment", "answer_span_in_evidence"}

    def test_answer_found_in_the_right_sentence_of_longer_evidence(self, ns):
        evidence = ("Albert Einstein was born in Ulm. He later moved to Switzerland. " + EINSTEIN_EVIDENCE +
                    " He received the Nobel Prize for the photoelectric effect.")
        r = run(ns, EINSTEIN_Q, evidence, "1905")
        c = r["verification"]["claims"][0]
        assert c["status"] == "SUPPORTED", c
        assert "annus mirabilis" in c["evidence"]

    def test_abstention_is_retried_and_still_verified(self, ns):
        """Generator abstains first; the plain retry answers. The retry is verified normally."""
        r = run(ns, EINSTEIN_Q, EINSTEIN_EVIDENCE,
                "I don't have enough information to answer this question.", plain="1905")
        assert r["generation_retried"] is True
        assert r["generated_answer"] == "1905"
        assert r["verification"]["claims"][0]["status"] == "SUPPORTED"

    def test_wrong_retry_is_not_trusted(self, ns):
        r = run(ns, EINSTEIN_Q, EINSTEIN_EVIDENCE,
                "I don't have enough information to answer this question.", plain="1999")
        assert r["verification"]["claims"][0]["status"] != "SUPPORTED"
        assert "1999" not in r["correction"]["corrected_answer"]


# ------------------------------------------------------------ genuinely unsupported
class TestUnsupported:
    @pytest.mark.parametrize("question,answer", [
        ("What year did Einstein win the Nobel Prize?", "1905"),   # copies the only year it sees
        ("Who won the 2010 football World Cup?", "Spain"),
        ("Which university did Einstein attend in Zurich?", "ETH Zurich"),
        ("How many children did Einstein have?", "Three"),
        ("Who published the four papers?", "Isaac Newton"),
    ])
    def test_not_supported_and_removed(self, ns, question, answer):
        r = run(ns, question, EINSTEIN_EVIDENCE, answer)
        claim = r["verification"]["claims"][0]
        assert claim["status"] != "SUPPORTED", claim
        assert answer not in r["correction"]["corrected_answer"]
        assert r["correction"]["correction_report"]["removed"] + \
            r["correction"]["correction_report"]["corrected"] == 1

    @pytest.mark.parametrize("answer", ["1905", "Einstein"])
    def test_abstention_stays_an_abstention(self, ns, answer):
        """The evidence does not answer this; an honest 'don't know' must not become an answer."""
        refusal = "I don't have enough information to answer this question."
        r = run(ns, "What is the capital of Australia?", EINSTEIN_EVIDENCE, refusal, plain=refusal)
        assert r["verification"]["claims"][0]["status"] == "NOT ENOUGH EVIDENCE"
        assert r["correction"]["corrected_answer"] == NOT_SUFFICIENT

    def test_unrelated_question_status_not_enough_evidence(self, ns):
        r = run(ns, "What is the boiling point of water?", EINSTEIN_EVIDENCE, "100")
        assert r["verification"]["claims"][0]["status"] == "NOT ENOUGH EVIDENCE"

    def test_two_years_in_one_sentence_is_ambiguous(self, ns):
        """A copied span is not proof when the sentence holds a competing year."""
        evidence = "In 1905 and in 1921, sometimes described as his annus mirabilis (miracle year), he published papers."
        assert not ns["answer_is_grounded"](EINSTEIN_Q, "1921", evidence)
        assert not ns["answer_is_grounded"](EINSTEIN_Q, "1905", evidence)


class TestNameEvidenceVerification:
    QUESTION = "what's my name?"
    EVIDENCE = "my name is pinc and im really glad to meet u"

    def test_name_explicitly_stated_is_supported(self, ns):
        report = ns["run_verification_pipeline"](
            self.QUESTION, self.EVIDENCE, "Pinc", verbose=False
        )
        claim = report["claims"][0]
        assert claim["hypothesis"] == "The person's name is Pinc."
        assert claim["status"] == "SUPPORTED", claim

    def test_name_absent_from_evidence_is_not_enough_evidence(self, ns):
        report = ns["run_verification_pipeline"](
            self.QUESTION, "It is nice to meet you.", "Pinc", verbose=False
        )
        assert report["claims"][0]["status"] == "NOT ENOUGH EVIDENCE"

    def test_different_evidenced_name_is_contradicted(self, ns):
        report = ns["run_verification_pipeline"](
            self.QUESTION, "My name is Alice.", "Pinc", verbose=False
        )
        assert report["claims"][0]["status"] == "CONTRADICTED"


# ------------------------------------------------------------- contradicted answers
class TestContradicted:
    @pytest.mark.parametrize("wrong", ["1906", "1921", "1895"])
    def test_wrong_year_is_contradicted_and_corrected(self, ns, wrong):
        r = run(ns, EINSTEIN_Q, EINSTEIN_EVIDENCE, wrong)
        claim = r["verification"]["claims"][0]
        assert claim["status"] == "CONTRADICTED", claim
        assert claim["number_consistent"] is False
        assert r["verification"]["overall_status"] == "CONTAINS HALLUCINATION"
        corrected = r["correction"]["corrected_answer"]
        assert wrong not in corrected and "1905" in corrected       # evidence-grounded fix
        assert r["correction"]["correction_report"]["corrected"] == 1

    def test_wrong_number_for_same_action_is_contradicted(self, ns):
        v = ns["run_verification_pipeline"]("How many people died in Kansas?", KANSAS,
                                            "Five people in Kansas have died from listeriosis.", verbose=False)
        assert v["claims"][0]["status"] == "CONTRADICTED"

    def test_nli_contradiction_is_honoured(self, ns_nli):
        r = run(ns_nli, EINSTEIN_Q, EINSTEIN_EVIDENCE, "Einstein published four papers in 1906.")
        assert r["verification"]["claims"][0]["status"] == "CONTRADICTED"
        assert "1906" not in r["correction"]["corrected_answer"]


# ------------------------------------------------- earlier behaviour must not regress
class TestExistingBehaviourPreserved:
    def test_eiffel_location(self, ns):
        r = run(ns, "Where is the Eiffel Tower located?", EIFFEL, "Paris, France")
        assert r["verification"]["claims"][0]["status"] == "SUPPORTED"
        assert r["correction"]["corrected_answer"] == "Paris, France"

    def test_eiffel_year_untouched(self, ns):
        r = run(ns, "When was the Eiffel Tower completed?", EIFFEL, "1889")
        assert r["verification"]["claims"][0]["status"] == "SUPPORTED"
        assert r["correction"]["corrected_answer"] == "1889"

    def test_eiffel_wrong_year_not_supported(self, ns):
        c = run(ns, "When was the Eiffel Tower completed?", EIFFEL, "1887")["verification"]["claims"][0]
        assert c["status"] != "SUPPORTED" and c["number_consistent"] is False

    def test_kansas_bare_count(self, ns):
        r = run(ns, "How many people were infected in the Kansas listeria outbreak?", KANSAS, "Five")
        c = r["verification"]["claims"][0]
        assert c["status"] == "SUPPORTED" and c["number_consistent"] is True

    def test_unsupported_sentence_removed(self, ns):
        r = run(ns, "What caused the outbreak?", KANSAS,
                "The outbreak was caused by contaminated spinach imported from Texas.")
        assert "spinach" not in r["correction"]["corrected_answer"].lower()

    def test_full_sentence_claims_use_the_old_path(self, ns):
        c = run(ns, "Where is it?", EIFFEL, "The Eiffel Tower is located in Paris.")["verification"]["claims"][0]
        assert c["hypothesis"] == c["claim"]               # unchanged for sentences
        assert c["question_coverage"] == 0.0

    def test_claim_splitting_still_works(self, ns):
        parts = ns["split_claims"]("Thomas purchased a ticket to Barcelona but was arrested before her trip.")
        assert len(parts) == 2 and parts[1].startswith("Thomas was arrested")

    def test_entity_and_number_checks_unchanged(self, ns):
        assert ns["check_entity_consistency"]("Asia Siddiqui was arrested in New York.",
            "Noelle Velentzas and her roommate, Asia Siddiqui, were arrested in New York.")["consistent"]
        assert ns["check_number_consistency"]("Seven", KANSAS)["consistent"] is False
        assert ns["check_number_consistency"]("1887", EIFFEL)["consistent"] is False
        assert ns["check_number_consistency"]("1905", EINSTEIN_EVIDENCE)["consistent"] is True


# --------------------------------------------- the notebook's own built-in test cells
def test_notebook_builtin_model_free_cells_pass(make_ns):
    """Re-run the model-free assertion cells that live inside the notebook.

    Four cells: correction safety, upload/chunking, status-decision rules and the
    short-answer helpers. (A fifth cell tested the automatic web-retrieval mode,
    which was removed from the final demo scope.)
    """
    import json
    from notebook_harness import default_notebook_path, _clean
    from stubs import FakeNLI
    ns = make_ns(FakeNLI)
    nb = json.load(open(default_notebook_path(), encoding="utf-8"))
    markers = [
    "def _fake(claim",
    "def _write_tmp",
    "def _nc(consistent",
    "Short-answer helper tests passed",
]
    shared = dict(ns)
    shared["MANDELA_EVIDENCE"] = (
    "Mandela was appointed President of the ANC's Transvaal branch, rising to prominence "
    "for his involvement in the 1952 Defiance Campaign and the 1955 Congress of the People. "
    "He was repeatedly arrested for seditious activities and was unsuccessfully prosecuted "
    "in the 1956 Treason Trial. Influenced by Marxism, he secretly joined the South African "
    "Communist Party (SACP). Although initially committed to non-violent protest, in "
    "association with the SACP he co-founded the militant Umkhonto we Sizwe in 1961 and led "
    "a sabotage campaign against the government. In 1962, he was arrested for conspiring to "
    "overthrow the state and sentenced to life imprisonment in the Rivonia Trial."
)
    ran = 0
            # one shared namespace: later cells reuse earlier helpers
    for cell in nb["cells"]:
        src = "".join(cell["source"])
        if cell["cell_type"] == "code" and any(m in src for m in markers):
            exec(compile(_clean(src), "builtin", "exec"), shared)
            ran += 1
    assert ran == 4
