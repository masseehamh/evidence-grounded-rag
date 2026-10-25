import os, sys
import pytest
sys.path.insert(0, os.path.dirname(__file__))
from notebook_harness import load_notebook
from stubs import FakeNLI, AlwaysNeutralNLI


@pytest.fixture(scope="session")
def make_ns():
    cache = {}

    def _make(nli_cls=FakeNLI, with_api=False):
        key = (nli_cls, with_api)
        if key not in cache:
            cache[key] = load_notebook(nli=nli_cls(), with_api=with_api)
        return cache[key]
    return _make


@pytest.fixture(params=[FakeNLI, AlwaysNeutralNLI], ids=["realistic-nli-stub", "worst-case-neutral-nli"])
def ns(request, make_ns):
    """Notebook namespace under two NLI behaviours. The Einstein fix must hold
    even when NLI never says 'entailment' (worst case)."""
    return make_ns(request.param)


@pytest.fixture
def ns_nli(make_ns):
    return make_ns(FakeNLI)


def script_generator(ns, first, plain=""):
    ns["generate_answer"] = lambda q, c, max_length=128: first
    ns["generate_answer_plain"] = lambda q, c, max_length=128: plain
