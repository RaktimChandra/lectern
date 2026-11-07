"""Helpers for turning model replies into JSON and preparing schemas for providers."""

from __future__ import annotations

import copy
import json
import re

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> dict:
    """Return the first JSON object in `text`.

    Models sometimes wrap JSON in code fences or add a sentence before it. This
    accepts those cases but never guesses at broken JSON.
    """
    text = text.strip()
    candidates = [text]
    candidates += [m.group(1).strip() for m in _FENCE.finditer(text)]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("no JSON object found in the reply")


def inline_schema(schema: dict) -> dict:
    """Resolve `$ref`s into a single self-contained schema.

    Some providers reject `$defs`/`$ref`; inlining keeps one schema format for all.
    """
    schema = copy.deepcopy(schema)
    defs = schema.pop("$defs", {})

    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].split("/")[-1]
                merged = {**resolve(copy.deepcopy(defs[name])), **{k: v for k, v in node.items() if k != "$ref"}}
                return merged
            return {k: resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(schema)
