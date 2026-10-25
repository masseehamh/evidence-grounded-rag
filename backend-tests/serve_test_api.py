"""Start the notebook's REAL FastAPI app on localhost with stand-in models, for end-to-end tests.

    python serve_test_api.py            # serves http://127.0.0.1:8765

Adds one test-only route, POST /__set_answer, to script what the (stand-in) generator
says. The notebook itself is not modified.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import uvicorn
from pydantic import BaseModel
from notebook_harness import load_notebook

ns = load_notebook(with_api=True)
_state = {"answer": "1905"}
ns["generate_answer"] = lambda q, c, max_length=128: _state["answer"]
ns["generate_answer_plain"] = lambda q, c, max_length=128: ""


class SetAnswer(BaseModel):
    answer: str


@ns["app"].post("/__set_answer")
def set_answer(body: SetAnswer):
    _state["answer"] = body.answer
    return {"answer": body.answer}


if __name__ == "__main__":
    uvicorn.run(ns["app"], host="127.0.0.1", port=int(os.environ.get("PORT", "8765")), log_level="warning")
