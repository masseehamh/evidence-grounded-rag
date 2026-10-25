"""Load the project's real notebook code into a namespace for testing.

Runs the notebook's own code cells (not a copy), skipping only what needs the
internet / GPU / UI: pip installs, model downloads, RAGTruth, Gradio, ngrok and
the slow evaluation loops.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from stubs import FakeRetriever, FakeNLI  # noqa: E402

# A cell is executed if it contains one of these markers.
CELL_MARKERS = [
    "CONFIG = {",
    "def split_into_sentences",
    "def find_subject",
    "def retrieve_evidence(",
    "def retrieve_diverse_evidence",
    "def prepare_retrieval_context",
    "def retrieve_evidence_fast",
    "def verify_claim(",
    "number_words = {",
    "def extract_all_numbers",
    "def extract_entities",
    "def check_entity_consistency",
    "def is_short_answer_fragment",          # added by the fix
    "def question_relation_is_missing",
    "def analyze_answer_improved",
    "def run_verification_pipeline",
    "def attempt_correction",
    "def run_full_rag_pipeline",
    "def md_safe",
    "def read_uploaded_txt",
    "def run_document_rag",
    "def is_public_http_url",
]
API_MARKER = "app = FastAPI("
API_STOP = "# Start the API in the background"
WEB_STOP = "web_demo = gr.Interface("


def _clean(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith(("!", "%")))


def default_notebook_path():
    here = os.path.dirname(os.path.abspath(__file__))
    env = os.environ.get("RAG_NOTEBOOK")
    if env:
        return env
    for name in sorted(os.listdir(os.path.dirname(here))):
        if name.endswith(".ipynb"):
            return os.path.join(os.path.dirname(here), name)
    raise FileNotFoundError("Set RAG_NOTEBOOK to the notebook path.")


def load_notebook(path=None, nli=None, generator=None, plain_generator=None, with_api=False):
    path = path or default_notebook_path()
    nb = json.load(open(path, encoding="utf-8"))
    import spacy, re, json as _json, time, hashlib, numpy as np
    ns = {
        "re": re, "json": _json, "time": time, "hashlib": hashlib, "np": np, "os": os,
        "__name__": "notebook_under_test",
        "retriever": FakeRetriever(),
        "verifier": nli or FakeNLI(),
        "nlp": spacy.load("en_core_web_sm"),
        "tokenizer": (lambda text, **_: {"input_ids": str(text).split()}),
        "generation_model": None,
    }
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        src = "".join(cell["source"])
        if API_MARKER in src:
            if with_api:
                exec(compile(_clean(src.split(API_STOP)[0]), "api_cell", "exec"), ns)
            continue
        if not any(m in src for m in CELL_MARKERS):
            continue
        if WEB_STOP in src:
            src = src.split(WEB_STOP)[0]
        exec(compile(_clean(src), f"cell:{cell.get('id')}", "exec"), ns)
    # Generation is a model call: scripted by each test.
    ns["generate_answer"] = generator or (lambda q, c, max_length=128: "")
    ns["generate_answer_plain"] = plain_generator or (lambda q, c, max_length=128: "")
    return ns
