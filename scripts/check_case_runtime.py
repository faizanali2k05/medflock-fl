"""Authenticated synthetic regression probe; credentials are read interactively."""

import argparse
import getpass
import json
import re
import ssl
import time
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--ca", type=Path)
    parser.add_argument(
        "--fixture", type=Path, default=Path("tests/fixtures/cardiology/chest-pain.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    if not fixture.get("synthetic"):
        raise ValueError("Only synthetic regression fixtures are accepted")
    context = ssl.create_default_context(cafile=str(args.ca) if args.ca else None)
    with httpx.Client(base_url=args.url, verify=context, timeout=930) as client:
        login = client.post(
            "/api/auth/login", json={"username": args.username, "password": getpass.getpass()}
        )
        login.raise_for_status()
        client.headers["X-CSRF-Token"] = login.json()["csrf"]
        started = time.monotonic()
        first = None
        result = None
        with client.stream(
            "POST",
            "/api/llm/generate-stream",
            json={
                "prompt": fixture["prompt"],
                "synthetic_only": True,
                "mode": "organize",
            },
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                item = json.loads(line[6:])
                if item["type"] == "draft" and first is None:
                    first = time.monotonic() - started
                if item["type"] == "error":
                    raise RuntimeError(item["detail"])
                if item["type"] == "complete":
                    result = item["result"]
        client.post("/api/auth/logout")
    if result is None:
        raise RuntimeError("Stream ended without completion")
    answer = result["answer"]
    failed = [
        pattern for pattern in fixture["required_patterns"] if not re.search(pattern, answer, re.I)
    ]
    failed += [
        pattern for pattern in fixture["forbidden_patterns"] if re.search(pattern, answer, re.I)
    ]
    report = {
        "fixture": fixture["id"],
        "first_draft_seconds": first,
        "result": result,
        "failed_patterns": failed,
        "clinical_validation": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "first_draft_seconds": first,
                "seconds": result["seconds"],
                "truncated": result["truncated"],
                "failed_patterns": failed,
            }
        )
    )
    if failed or result["truncated"] or result.get("quality_warnings"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
