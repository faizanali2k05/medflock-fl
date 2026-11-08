"""Stream draft text while keeping provider reasoning channels out of the UI."""

import json
import re
import time

import httpx

from medflock.response_checks import reject_repetition


def complete_stream(url, payload, timeout, progress):
    text = ""
    emitted = 0
    usage = {}
    finish = None
    started = time.monotonic()
    with httpx.stream(
        "POST",
        url,
        json={**payload, "stream": True, "stream_options": {"include_usage": True}},
        timeout=httpx.Timeout(timeout, connect=3),
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if time.monotonic() - started > timeout:
                raise httpx.ReadTimeout("Generation deadline exceeded")
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            chunk = json.loads(data)
            if chunk.get("error"):
                raise ValueError("Model streaming error")
            usage = chunk.get("usage") or usage
            for choice in chunk.get("choices", []):
                text += choice.get("delta", {}).get("content") or ""
                finish = choice.get("finish_reason") or finish
            reject_repetition(text)
            if len(text) >= 16 and not re.match(
                r"\s*(?:thought\b|analysis\b|<think>)", text, flags=re.IGNORECASE
            ):
                progress(text[emitted:])
                emitted = len(text)
    if finish is None:
        raise ValueError("Model stream ended before completion")
    return {"choices": [{"message": {"content": text}, "finish_reason": finish}], "usage": usage}
