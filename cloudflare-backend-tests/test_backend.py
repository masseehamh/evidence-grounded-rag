import subprocess
import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import app as backend


class LightweightBackendTests(unittest.TestCase):
    def test_python_module_imports_without_ml_packages(self):
        backend_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "backend")
        )

        script = (
            "import sys\n"
            f"sys.path.insert(0, {backend_dir!r})\n"
            "import app\n"
            "assert app.APP_VERSION == '2.0.0'\n"
            "for package in ('torch', 'transformers', 'spacy'):\n"
            "    assert package not in sys.modules, "
            "f'{package} was imported'\n"
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            result.returncode,
            0,
            msg=result.stderr or result.stdout,
        )

    def test_missing_cloudflare_environment_is_reported(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(backend.cloudflare_configuration(), (None, None))
            health = backend.api_health()
            self.assertFalse(health["cloudflare_configured"])

    def test_numeric_extraction_and_mismatch(self):
        self.assertEqual(backend.extract_numbers("Accuracy was 91% on 120 examples."), {"91", "120"})
        ok, _ = backend.numeric_consistency(
            "Accuracy was 95%.", "The measured accuracy was 91%."
        )
        self.assertFalse(ok)

    def test_supported_answer_and_frontend_fields(self):
        def fake_chat(messages, max_tokens=700):
            prompt = messages[-1]["content"]
            if "Give a concise answer" in prompt:
                return "The test set contained 120 examples. Accuracy was 91%."
            return (
                '{"claims":['
                '{"claim":"The test set contained 120 examples.","status":"SUPPORTED",'
                '"evidence":"The test set contained 120 examples.","reason":"Directly stated."},'
                '{"claim":"Accuracy was 91%.","status":"SUPPORTED",'
                '"evidence":"Measured accuracy was 91%.","reason":"Directly stated."}'
                ']}'
            )
        with patch.object(backend, "cloudflare_chat", side_effect=fake_chat):
            result = backend.run_rag(
                "What was the test size and accuracy?",
                "The test set contained 120 examples. Measured accuracy was 91%."
            )
        required = {
            "verification_status", "original_answer", "corrected_answer",
            "corrected_status", "corrected_evidence", "claims", "removed_claims", "sources"
        }
        self.assertTrue(required.issubset(result.keys()))
        self.assertEqual(result["corrected_status"], "SUPPORTED")
        self.assertEqual(len(result["claims"]), 2)

    def test_unsupported_claim_is_removed(self):
        def fake_chat(messages, max_tokens=700):
            prompt = messages[-1]["content"]
            if "Give a concise answer" in prompt:
                return "The prototype reduced hallucinations by 40%."
            return (
                '{"claims":[{"claim":"The prototype reduced hallucinations by 40%.",'
                '"status":"NOT_ENOUGH_EVIDENCE","evidence":"",'
                '"reason":"No reduction result is reported."}]}'
            )
        with patch.object(backend, "cloudflare_chat", side_effect=fake_chat):
            result = backend.run_rag(
                "What reduction was reported?",
                "The prototype was evaluated on 120 examples. No results were reported for a 40% reduction."
            )
        self.assertEqual(result["corrected_status"], "NOT_ENOUGH_EVIDENCE")
        self.assertEqual(len(result["removed_claims"]), 1)
        self.assertIn("not contain enough information", result["corrected_answer"])

    def test_contradiction_is_reported_and_removed(self):
        def fake_chat(messages, max_tokens=700):
            prompt = messages[-1]["content"]
            if "Give a concise answer" in prompt:
                return "Accuracy was 95%."
            return (
                '{"claims":[{"claim":"Accuracy was 95%.","status":"CONTRADICTED",'
                '"evidence":"Measured accuracy was 91%.","reason":"The values conflict."}]}'
            )
        with patch.object(backend, "cloudflare_chat", side_effect=fake_chat):
            result = backend.run_rag(
                "What was accuracy?",
                "Measured accuracy was 91%."
            )
        self.assertEqual(result["claims"][0]["status"], "CONTRADICTED")
        self.assertEqual(result["corrected_status"], "NOT_ENOUGH_EVIDENCE")

    def test_model_json_parser_handles_fence(self):
        parsed = backend.parse_json_object('```json\n{"claims": []}\n```')
        self.assertEqual(parsed, {"claims": []})

    def test_openai_response_shape_is_checked(self):
        # Test response-format parsing logic indirectly by supplying invalid JSON
        # from the model verifier; the pipeline must not silently mark it supported.
        def fake_chat(messages, max_tokens=700):
            if "Give a concise answer" in messages[-1]["content"]:
                return "A claim."
            return "not json"
        with patch.object(backend, "cloudflare_chat", side_effect=fake_chat):
            with self.assertRaises(ValueError):
                backend.run_rag("What is stated?", "The evidence is present.")


    def test_cloudflare_openai_compatible_response_shape(self):
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self):
                return b'{"choices":[{"message":{"content":"mock answer"}}]}'
        with patch.dict(os.environ, {
            "CLOUDFLARE_ACCOUNT_ID": "test-account",
            "CLOUDFLARE_API_TOKEN": "test-token",
        }, clear=True), patch.object(backend, "urlopen", return_value=FakeResponse()) as mocked:
            content = backend.cloudflare_chat([{"role": "user", "content": "test"}])
        self.assertEqual(content, "mock answer")
        request = mocked.call_args.args[0]
        self.assertIn("/ai/v1/chat/completions", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")

    def test_cloudflare_http_401_is_actionable_and_does_not_leak_token(self):
        from urllib.error import HTTPError
        from io import BytesIO
        error = HTTPError(
            url="https://example.invalid", code=401, msg="Unauthorized",
            hdrs=None, fp=BytesIO(b'{"errors":[{"message":"bad token"}]}')
        )
        with patch.dict(os.environ, {
            "CLOUDFLARE_ACCOUNT_ID": "test-account",
            "CLOUDFLARE_API_TOKEN": "secret-not-for-output",
        }, clear=True), patch.object(backend, "urlopen", side_effect=error):
            with self.assertRaises(RuntimeError) as caught:
                backend.cloudflare_chat([{"role": "user", "content": "test"}])
        self.assertIn("HTTP 401", str(caught.exception))
        self.assertNotIn("secret-not-for-output", str(caught.exception))

    def test_text_upload_validation(self):
        self.assertEqual(backend.validate_text_file("a.txt", b"Hello"), "Hello")
        with self.assertRaises(HTTPException):
            backend.validate_text_file("a.pdf", b"Hello")
        with self.assertRaises(HTTPException):
            backend.validate_text_file("a.txt", b"\x00bad")
        with self.assertRaises(HTTPException):
            backend.validate_text_file("a.txt", b" " * (backend.MAX_UPLOAD_BYTES + 1))

    def test_document_retrieval_and_source_contract(self):
        passages = backend.retrieve_document_context(
            "What was accuracy?",
            "The test used 120 examples. Accuracy was 91%. The sky is blue."
        )
        self.assertTrue(passages)
        self.assertIn("Accuracy was 91%.", " ".join(item[0] for item in passages))
        response = backend.make_insufficient_response([{"title": "report.txt", "url": "", "passage": "text"}])
        self.assertEqual(response["sources"][0]["title"], "report.txt")
        self.assertIn("corrected_evidence", response)


if __name__ == "__main__":
    unittest.main()
