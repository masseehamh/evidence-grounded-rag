"""Small helpers shared by the controlled runner and offline evaluator."""
from __future__ import annotations

import json
import re


def parse_selective_json(response: str) -> tuple[dict | None, str]:
    """Parse the selective response object, accepting optional Markdown fences."""
    text = response.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    candidate = fenced.group(1).strip() if fenced else text
    try:
        parsed = json.loads(candidate)
        if not isinstance(parsed, dict):
            return None, "invalid_json_not_object"
        return parsed, "valid_json_fenced" if fenced else "valid_json"
    except json.JSONDecodeError:
        return None, "invalid_json"


def extract_answer(strategy: str, response: str) -> tuple[str, str]:
    """Extract the user-facing answer, accepting JSON optionally wrapped in fences."""
    if strategy != "selective_correction":
        return response.strip(), "not_applicable"
    parsed, status = parse_selective_json(response)
    answer = parsed.get("answer") if parsed else None
    if isinstance(answer, str) and not answer.strip():
        # An explicit empty answer is a valid abstention, not a parse failure.
        return "", f"{status}_empty_answer"
    if not isinstance(answer, str):
        return response.strip(), "invalid_json_missing_answer" if parsed else status
    return answer.strip(), status
