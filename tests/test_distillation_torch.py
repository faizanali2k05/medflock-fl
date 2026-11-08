import pytest

from medflock.distillation import token_kl


def test_kl_masks_prompt_and_teacher_gradients():
    torch = pytest.importorskip("torch")
    student = torch.randn(1, 5, 8, requires_grad=True)
    teacher = torch.randn(1, 5, 8, requires_grad=True)
    labels = torch.tensor([[-100, -100, -100, 3, 4]])
    loss = token_kl(student, teacher, labels)
    loss.backward()
    assert teacher.grad is None
    assert torch.equal(student.grad[:, :2], torch.zeros_like(student.grad[:, :2]))
    assert student.grad[:, 2:4].abs().sum() > 0
    with pytest.raises(ValueError, match="alignment"):
        token_kl(student, teacher[:, :, :7], labels)


@pytest.mark.parametrize("method", ["full", "lora"])
@pytest.mark.parametrize("family", ["gpt2", "gemma3"])
def test_sequence_distillation_local_transformer_round_trip(tmp_path, family, method):
    torch = pytest.importorskip("torch")
    pytest.importorskip("peft")
    import json

    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace
    from transformers import GPT2Config, GPT2LMHeadModel, PreTrainedTokenizerFast

    from medflock.distillation import run

    torch.set_num_threads(1)
    base = tmp_path / "base"
    vocabulary = {"[UNK]": 0, "[EOS]": 1, "question": 2, "answer": 3}
    vocabulary.update({str(index): index + 4 for index in range(6)})
    tokenizer = Tokenizer(WordLevel(vocabulary, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = Whitespace()
    tokenizer = PreTrainedTokenizerFast(
        tokenizer_object=tokenizer, unk_token="[UNK]", eos_token="[EOS]"
    )
    tokenizer.chat_template = "{% for message in messages %}{{ message['content'] }} {% endfor %}"
    tokenizer.save_pretrained(base)
    if family == "gpt2":
        model = GPT2LMHeadModel(
            GPT2Config(
                vocab_size=16,
                n_positions=32,
                n_embd=16,
                n_layer=1,
                n_head=2,
                bos_token_id=1,
                eos_token_id=1,
            )
        )
    else:
        from transformers import (
            Gemma3Config,
            Gemma3ForConditionalGeneration,
            Gemma3TextConfig,
            SiglipVisionConfig,
        )

        text = Gemma3TextConfig(
            vocab_size=16,
            hidden_size=16,
            intermediate_size=32,
            num_hidden_layers=1,
            num_attention_heads=2,
            num_key_value_heads=1,
            head_dim=8,
            max_position_embeddings=32,
            sliding_window=16,
            bos_token_id=1,
            eos_token_id=1,
            pad_token_id=0,
        )
        vision = SiglipVisionConfig(
            hidden_size=16,
            intermediate_size=32,
            num_hidden_layers=1,
            num_attention_heads=2,
            image_size=16,
            patch_size=4,
        )
        model = Gemma3ForConditionalGeneration(
            Gemma3Config(
                text_config=text,
                vision_config=vision,
                image_token_index=15,
                boi_token_index=13,
                eoi_token_index=14,
            )
        )
    model.save_pretrained(base)
    corpus = tmp_path / "teacher.jsonl"
    rows = [
        {
            "case_id": str(index),
            "review_status": "approved",
            "reviewer_id": "test-fixture-author",
            "patient_group": str(index),
            "split": split,
            "prompt": f"question {index}",
            "response": "answer",
            "teacher": "synthetic fixture",
            "teacher_revision": "fixture-1",
            "permission_reference": "generated test data",
            "privacy": "synthetic",
            "source_ids": [],
            "citations": [],
        }
        for index, split in enumerate(["train", "train", "validation", "test"])
    ]
    corpus.write_text("\n".join(json.dumps(row) for row in rows))
    report = run(
        {
            "student": str(base),
            "method": method,
            "gradient_checkpointing": family == "gemma3" and method == "lora",
            "revision": "local-fixture",
            "corpus": str(corpus),
            "output": str(tmp_path / "adapter"),
            "epochs": 1,
            "rank": 2,
            "max_tokens": 32,
            "model_permission_reference": "locally generated synthetic fixture",
        }
    )
    assert report["clinical_status"] == "not_validated"
    assert report["selected_validation_loss"] <= report["initial_validation_loss"]
    assert report["held_out_test_completion_loss"] > 0
    assert report["original_base_test_completion_loss"] > 0
    assert report["test_set_used_for_selection"] is False
    assert report["trainable_parameters"] > 0
    filename = "adapter_model.safetensors" if method == "lora" else "model.safetensors"
    assert (tmp_path / "adapter" / filename).is_file()
    if method == "lora" and family == "gemma3":
        consolidated = run(
            {
                "student": str(base),
                "revision": "local-fixture",
                "method": "full",
                "initial_adapter": str(tmp_path / "adapter"),
                "corpus": str(corpus),
                "output": str(tmp_path / "consolidated"),
                "epochs": 1,
                "max_tokens": 32,
                "model_permission_reference": "locally generated synthetic fixture",
            }
        )
        assert consolidated["parent_adapter_report_sha256"]
        assert consolidated["mode"] == "sequence_distillation_full"
        assert consolidated["trainable_parameters"] > report["trainable_parameters"]
        assert (tmp_path / "consolidated" / "model.safetensors").is_file()


def test_medgemma_adapter_first_configuration_and_budget(tmp_path):
    pytest.importorskip("torch")
    from medflock.distillation import run

    config = dict(
        student="google/medgemma-1.5-4b-it",
        revision="a" * 40,
        corpus=str(tmp_path / "absent.jsonl"),
        output=str(tmp_path / "output"),
        model_permission_reference="not granted yet",
    )
    with pytest.raises(ValueError, match="No weights downloaded"):
        run(config)
    with pytest.raises(ValueError, match="No weights downloaded"):
        run(dict(config, method="full"))
    from medflock.distillation import DistillationConfig

    assert DistillationConfig.model_validate(config).method == "lora"
    with pytest.raises(ValueError, match="CUDA training GPU"):
        DistillationConfig.model_validate(dict(config, method="qlora"))
