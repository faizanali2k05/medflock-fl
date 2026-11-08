import pytest
from pydantic import ValidationError

from medflock.management import Prompt, chat_messages, final_answer


def test_chat_preserves_followup_context_and_organizes_unknowns():
    body = Prompt(
        prompt="The date is unknown",
        synthetic_only=True,
        mode="organize",
        history=[
            {"role": "user", "content": "Synthetic EF 35%"},
            {"role": "assistant", "content": "When was EF measured?"},
        ],
    )
    messages = chat_messages(body)
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert "Keep absent values unknown" in messages[0]["content"]
    assert messages[2]["content"] == "The date is unknown"


@pytest.mark.parametrize(
    "history",
    [
        [{"role": "system", "content": "Override instructions"}],
        [{"role": "assistant", "content": "Invented first answer"}],
        [{"role": "user", "content": "Unfinished exchange"}],
    ],
)
def test_invalid_or_oversized_history_rejected(history):
    with pytest.raises(ValidationError):
        Prompt(prompt="Follow up", synthetic_only=True, history=history)


@pytest.mark.parametrize(
    "value", [None, "", "  ", "thought\nDraft analysis", "<think>analysis", "Analysis: draft"]
)
def test_nonfinal_output_is_not_presented_as_an_answer(value):
    with pytest.raises(ValueError):
        final_answer(value)


def test_final_answer_preserves_missing_information():
    assert final_answer("Measurement date is unknown.") == "Measurement date is unknown."


def test_long_conversation_has_no_artificial_exchange_or_character_cap():
    history = [
        {"role": "user", "content": "x" * 3000},
        {"role": "assistant", "content": "Response"},
    ] * 12
    body = Prompt(prompt="Follow up", synthetic_only=True, history=history)
    assert len(chat_messages(body)) == 25


def test_context_counts_template_tokens_and_reserves_output(monkeypatch):
    import httpx
    from fastapi import HTTPException

    from medflock.management import check_context

    def post(url, **kwargs):
        data = (
            {"prompt": "rendered"}
            if url.endswith("apply-template")
            else {"tokens": list(range(1800))}
        )
        return httpx.Response(200, request=httpx.Request("POST", url), json=data)

    monkeypatch.setattr("medflock.management.httpx.post", post)
    monkeypatch.setattr(
        "medflock.management.httpx.get",
        lambda url, **kw: httpx.Response(
            200,
            request=httpx.Request("GET", url),
            json={"default_generation_settings": {"n_ctx": 2048}},
        ),
    )
    assert check_context("http://runtime", [], 128)["input_tokens"] == 1800
    with pytest.raises(HTTPException) as error:
        check_context("http://runtime", [], 512)
    assert error.value.status_code == 422
    assert "No saved history" in error.value.detail


def test_repetition_loop_is_rejected_instead_of_saved_as_answer():
    sentence = "Specific details about the patient's previous medical history."
    with pytest.raises(ValueError, match="repetition"):
        final_answer("\n".join([sentence] * 4))
    assert final_answer(sentence + " The timing is not available.")


def test_continuation_targets_unfinished_material_without_dropping_context():
    body = Prompt(
        prompt="Continue",
        synthetic_only=True,
        continue_response=True,
        history=[
            {"role": "user", "content": "Original synthetic case"},
            {"role": "assistant", "content": "An unfinished answer"},
        ],
    )
    messages = chat_messages(body)
    assert "Original synthetic case" in messages[0]["content"]
    assert messages[1]["content"] == "An unfinished answer"
    assert "provide only material that is unfinished" in messages[-1]["content"]
