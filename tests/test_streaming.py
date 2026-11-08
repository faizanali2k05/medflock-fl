import json
from contextlib import contextmanager
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from medflock.api import create_app
from medflock.config import Settings
from medflock.streaming import complete_stream


@pytest.mark.parametrize(
    "text,visible", [("A complete final response.", True), ("thought\nPrivate reasoning", False)]
)
def test_stream_ignores_reasoning_channel_and_requires_finish(monkeypatch, text, visible):
    class Response:
        def raise_for_status(self):
            pass

        def iter_lines(self):
            for delta in [{"reasoning_content": "Private reasoning"}, {"content": text}]:
                yield "data: " + json.dumps({"choices": [{"delta": delta}]})
            yield "data: " + json.dumps(
                {
                    "choices": [{"delta": {}, "finish_reason": "stop"}],
                    "usage": {"completion_tokens": 6},
                }
            )
            yield "data: [DONE]"

    @contextmanager
    def stream(*args, **kwargs):
        yield Response()

    monkeypatch.setattr("medflock.streaming.httpx.stream", stream)
    parts = []
    result = complete_stream("http://runtime", {}, 30, parts.append)
    assert bool(parts) == visible
    assert result["choices"][0]["message"]["content"] == text
    assert result["usage"]["completion_tokens"] == 6


def test_stream_endpoint_keeps_auth_and_delivers_completion(tmp_path, monkeypatch):
    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'stream.db'}",
        dataset=tmp_path / "absent.csv",
        artifacts=tmp_path / "artifacts",
        settings=replace(
            Settings.load(), auth_required=True, api_key="x" * 40, embedded_worker=False
        ),
    )

    def generate(body, request, principal, progress):
        progress("Unreviewed draft")
        return {"answer": "Completed draft"}

    monkeypatch.setattr("medflock.management.run_generation", generate)
    with TestClient(app) as client:
        body = {"prompt": "Synthetic case", "synthetic_only": True}
        assert client.post("/api/llm/generate-stream", json=body).status_code == 401
        result = client.post(
            "/api/llm/generate-stream", json=body, headers={"Authorization": "Bearer " + "x" * 40}
        )
        assert result.status_code == 200
        events = [
            json.loads(line[6:]) for line in result.text.splitlines() if line.startswith("data: ")
        ]
        assert [e["type"] for e in events] == ["draft", "complete"]
        assert events[-1]["result"]["answer"] == "Completed draft"


def test_stream_aborts_repeated_bullets_before_completion(monkeypatch):
    from medflock.response_checks import RepetitionError

    class Response:
        def raise_for_status(self):
            pass

        def iter_lines(self):
            for _ in range(10):
                yield "data: " + json.dumps(
                    {
                        "choices": [
                            {
                                "delta": {
                                    "content": (
                                        "Specific details about the patient's "
                                        "previous medical history.\n"
                                    )
                                }
                            }
                        ]
                    }
                )

    @contextmanager
    def stream(*args, **kwargs):
        yield Response()

    monkeypatch.setattr("medflock.streaming.httpx.stream", stream)
    parts = []
    with pytest.raises(RepetitionError):
        complete_stream("http://runtime", {}, 30, parts.append)
    assert len(parts) < 10
