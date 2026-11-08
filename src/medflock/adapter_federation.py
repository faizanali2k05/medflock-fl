"""LoRA rounds exchange compatible adapter tensors while keeping training records local."""

import hashlib
import json
from pathlib import Path

import numpy as np
from flwr.app import ArrayRecord, Message, MetricRecord, RecordDict

from medflock.distillation import (
    DistillationConfig,
    encode_case,
    load_corpus,
    require_reviewed_corpus,
)


def adapter_contract(model, tokenizer, config):
    from peft import get_peft_model_state_dict

    state = get_peft_model_state_dict(model)
    layout = [(key, list(state[key].shape)) for key in sorted(state)]
    local = Path(config.student)
    hashes = {}
    if local.is_dir():
        for file in sorted(local.glob("*.safetensors")):
            digest = hashlib.sha256()
            with file.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            hashes[file.name] = digest.hexdigest()
        if not hashes:
            raise ValueError("Local federated bases require safetensors checkpoints")
    identity = {
        "base": "verified-local-checkpoint" if hashes else config.student,
        "base_files": hashes,
        "task_id": config.task_id,
        "revision": config.revision,
        "rank": config.rank,
        "tokenizer": tokenizer.get_vocab(),
        "template": tokenizer.chat_template,
        "layout": layout,
    }
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return digest, layout


def arrays_from_adapter(model):
    from peft import get_peft_model_state_dict

    state = get_peft_model_state_dict(model)
    return [state[key].detach().float().cpu().numpy().copy() for key in sorted(state)]


def apply_adapter_arrays(model, arrays, layout):
    import torch
    from peft import set_peft_model_state_dict

    if len(arrays) != len(layout):
        raise ValueError("Adapter update tensor count mismatch")
    state = {}
    for (name, shape), array in zip(layout, arrays, strict=True):
        if list(array.shape) != shape or array.dtype != np.float32 or not np.isfinite(array).all():
            raise ValueError("Invalid adapter update shape, dtype or values")
        state[name] = torch.from_numpy(array.copy())
    set_peft_model_state_dict(model, state)


def local_adapter_batch(model, rows, device, learning_rate):
    import torch

    if not rows:
        raise ValueError("Local training split is empty")
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=learning_rate
    )
    model.train()
    optimizer.zero_grad(set_to_none=True)
    row = rows[0]
    loss = model(**{key: torch.tensor([value], device=device) for key, value in row.items()}).loss
    if not torch.isfinite(loss):
        raise ValueError("Local adapter loss is non-finite")
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    optimizer.step()
    return float(loss.detach())


def load_runner(path):
    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import (
        AutoConfig,
        AutoModelForCausalLM,
        AutoModelForImageTextToText,
        AutoTokenizer,
    )

    config = DistillationConfig.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
    if config.method not in {"lora", "qlora"}:
        raise ValueError("Hospital adapter rounds require LoRA or QLoRA")
    if config.initial_adapter:
        raise ValueError("Round initialization must come from the coordinator")
    if config.device.startswith("cuda") and not torch.cuda.is_available():
        raise ValueError("Configured hospital GPU is unavailable")
    if not Path(config.student).exists() and (
        len(config.revision) != 40 or any(c not in "0123456789abcdef" for c in config.revision)
    ):
        raise ValueError("Hospital base revision must be immutable")
    floor = 1.9 if config.method == "qlora" else (14.9 if config.precision == "float32" else 7.5)
    if "medgemma" in config.student.lower() and config.memory_budget_gib < floor:
        raise ValueError("MedGemma base alone exceeds the local memory budget")
    rows = load_corpus(config.corpus)
    require_reviewed_corpus(rows)
    tokenizer = AutoTokenizer.from_pretrained(
        config.student, revision=config.revision, trust_remote_code=False
    )
    architecture = AutoConfig.from_pretrained(
        config.student, revision=config.revision, trust_remote_code=False
    )
    loader = (
        AutoModelForImageTextToText if architecture.model_type == "gemma3" else AutoModelForCausalLM
    )
    options = {}
    if config.method == "qlora":
        from transformers import BitsAndBytesConfig

        options.update(
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=getattr(torch, config.precision),
            ),
            device_map={"": config.device},
        )
    torch.manual_seed(config.seed)
    model = loader.from_pretrained(
        config.student,
        revision=config.revision,
        torch_dtype=getattr(torch, config.precision),
        trust_remote_code=False,
        **options,
    )
    model.config.use_cache = False
    if config.method == "qlora":
        from peft import prepare_model_for_kbit_training

        model = prepare_model_for_kbit_training(
            model, use_gradient_checkpointing=config.gradient_checkpointing
        )
    else:
        model.to(config.device)
    model = get_peft_model(
        model,
        LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=config.rank,
            lora_alpha=config.rank * 2,
            lora_dropout=0.0,
            target_modules="all-linear",
        ),
    )
    if config.gradient_checkpointing and config.method != "qlora":
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()
    digest, layout = adapter_contract(model, tokenizer, config)
    encoded = [
        encode_case(tokenizer, row, config.max_tokens) for row in rows if row["split"] == "train"
    ]
    return config, model, encoded, digest, layout


def train_adapter_message(message, context):
    config, model, rows, digest, layout = load_runner(context.node_config["adapter-config"])
    if message.content["config"]["adapter-contract"] != digest:
        raise ValueError("Coordinator base/tokenizer/adapter contract mismatch")
    apply_adapter_arrays(model, message.content["arrays"].to_numpy_ndarrays(), layout)
    local_adapter_batch(model, rows, config.device, config.learning_rate)
    return Message(
        RecordDict(
            {
                "arrays": ArrayRecord(arrays_from_adapter(model)),
                "metrics": MetricRecord({"num-examples": 1}),
            }
        ),
        reply_to=message,
    )
