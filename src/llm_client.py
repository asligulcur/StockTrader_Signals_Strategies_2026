"""Anthropic Claude API wrapper with retries and JSON extraction."""

from __future__ import annotations

import json
import os
import re
import time

from anthropic import Anthropic

from src.config import ANTHROPIC_MODEL, MAX_OUTPUT_TOKENS, MAX_RETRIES, TEMPERATURE

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client


def _text_from_response(message) -> str:
    """Concatenate only text blocks (ignore thinking / tool blocks on newer models)."""
    parts: list[str] = []
    for block in message.content:
        if getattr(block, "type", None) == "text" and hasattr(block, "text"):
            parts.append(block.text)
    return "".join(parts).strip()


def _extract_json_object(text: str) -> dict | None:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def call_llm(
    system_prompt: str,
    user_prompt: str,
    max_retries: int | None = None,
    *,
    response_kind: str = "strategy",
) -> dict:
    """
    Call Anthropic Messages API and return parsed JSON dict.
    response_kind: 'strategy' -> expects decision/confidence/justification;
                   'evaluator' -> expects analysis only.
    """
    retries = max_retries if max_retries is not None else MAX_RETRIES
    client = _get_client()
    last_err = ""

    for attempt in range(retries):
        try:
            message = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=TEMPERATURE,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            content = _text_from_response(message)
            parsed = _extract_json_object(content)
            if parsed is not None:
                return parsed
            last_err = "Could not parse JSON from model response"
        except Exception as e:
            last_err = str(e)
        if attempt < retries - 1:
            time.sleep(1)

    if response_kind == "evaluator":
        return {"analysis": f"Evaluator failed after {retries} retries: {last_err}"}
    return {
        "decision": "ERROR",
        "confidence": 0,
        "justification": f"LLM call failed after {retries} retries: {last_err}",
    }
