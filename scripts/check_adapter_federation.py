"""Exercise one local Gemma training batch per node and aggregate Flower adapter messages."""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch
from flwr.app import ArrayRecord, ConfigRecord
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace
from transformers import Gemma3ForCausalLM, Gemma3TextConfig, PreTrainedTokenizerFast

from medflock.adapter_federation import apply_adapter_arrays, arrays_from_adapter, load_runner
from medflock.distillation import completion_loss
from medflock.federation import train_node
from medflock.federation_policy import HospitalFedAvg


def prepare(root):
    root.mkdir(parents=True, exist_ok=True)
    base = root / "tiny-gemma-base"
    torch.manual_seed(42)
    torch.set_num_threads(1)
    model = Gemma3ForCausalLM(
        Gemma3TextConfig(
            vocab_size=32,
            hidden_size=16,
            intermediate_size=32,
            num_hidden_layers=1,
            num_attention_heads=2,
            num_key_value_heads=1,
            head_dim=8,
            max_position_embeddings=128,
            sliding_window=64,
            bos_token_id=1,
            eos_token_id=1,
            pad_token_id=0,
        )
    )
    model.save_pretrained(base)
    tokenizer = Tokenizer(
        WordLevel(
            {"[UNK]": 0, "[EOS]": 1, "synthetic": 2, "question": 3, "answer": 4}, unk_token="[UNK]"
        )
    )
    tokenizer.pre_tokenizer = Whitespace()
    tokenizer = PreTrainedTokenizerFast(
        tokenizer_object=tokenizer, unk_token="[UNK]", eos_token="[EOS]"
    )
    tokenizer.chat_template = "{% for message in messages %}{{ message['content'] }} {% endfor %}"
    tokenizer.save_pretrained(base)
    configs = []
    for node in range(3):
        directory = root / f"hospital-{node}"
        directory.mkdir(exist_ok=True)
        rows = [
            {
                "case_id": f"{node}-{i}",
                "patient_group": f"{node}-{i}",
                "split": split,
                "prompt": f"synthetic question private-node-{node}-{i}",
                "response": "answer",
                "teacher": "software test fixture",
                "teacher_revision": "fixture-v1",
                "permission_reference": "generated synthetic software test",
                "privacy": "synthetic",
                "source_ids": [],
                "citations": [],
                "review_status": "approved",
                "reviewer_id": "software-fixture-author",
            }
            for i, split in enumerate(["train", "validation", "test"])
        ]
        corpus = directory / "local-only.jsonl"
        corpus.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
        settings = dict(
            student=str(base.resolve()),
            revision="local-test-v1",
            corpus=str(corpus.resolve()),
            output=str((directory / "unused-output").resolve()),
            method="lora",
            rank=2,
            max_tokens=64,
            learning_rate=0.001,
            model_permission_reference="synthetic fixture only",
            device="cpu",
        )
        path = directory / "runner.json"
        path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        configs.append(path.resolve())
    return configs


def check(root):
    configs = prepare(root)
    config, model, rows, digest, layout = load_runner(configs[0])
    initial = arrays_from_adapter(model)
    before = completion_loss(model, rows, "cpu")
    strategy = HospitalFedAvg(lambda: {11, 12, 13}, minimum=3)
    messages = list(
        strategy.configure_train(
            1,
            ArrayRecord(initial),
            ConfigRecord({"adapter-contract": digest}),
            SimpleNamespace(get_node_ids=lambda: [11, 12, 13]),
        )
    )
    replies = [
        train_node(message, SimpleNamespace(node_config={"adapter-config": str(path)}))
        for message, path in zip(messages, configs, strict=True)
    ]
    for reply in replies:
        assert set(reply.content.keys()) == {"arrays", "metrics"}
        assert set(reply.content["metrics"].keys()) == {"num-examples"}
        assert reply.content["metrics"]["num-examples"] == 1
    aggregated, _ = strategy.aggregate_train(1, replies)
    updated = aggregated.to_numpy_ndarrays()
    assert any(not np.array_equal(a, b) for a, b in zip(initial, updated, strict=True))
    apply_adapter_arrays(model, updated, layout)
    after = completion_loss(model, rows, "cpu")
    result = {
        "model": "tiny randomly initialized Gemma3 text fixture, not MedGemma",
        "clients": 3,
        "batches_per_client": 1,
        "payload_keys": ["arrays", "metrics"],
        "adapter_tensors": len(updated),
        "adapter_bytes": sum(a.nbytes for a in updated),
        "contract_sha256": digest,
        "local_completion_loss_before": before,
        "local_completion_loss_after": after,
        "weights_changed": True,
        "clinical_validation": False,
        "network_transport": "Flower Message objects; run flower_spike separately for real sockets",
    }
    (root / "evidence.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    bundle = root / "coordinator"
    bundle.mkdir(exist_ok=True)
    np.savez(
        bundle / "initial-adapter.npz", **{f"tensor-{i:04d}": v for i, v in enumerate(initial)}
    )
    (bundle / "server.json").write_text(
        json.dumps({"family": "causal-lora", "digest": digest, "layout": layout}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))
    return configs


if __name__ == "__main__":
    from flwr.supercore.task_identity import TaskIdentity

    TaskIdentity.run_id = 1
    TaskIdentity.node_id = 1
    TaskIdentity.task_id = 1
    check(Path("runtime/adapter-federation-check"))
