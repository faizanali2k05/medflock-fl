"""Completion-only sequence distillation keeps teacher provenance and held-out cases explicit."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DistillationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student: str
    task_id: str = Field(default="cardiology-text-v1", pattern=r"^[a-z0-9][a-z0-9_.-]{0,119}$")
    revision: str
    corpus: Path
    output: Path
    model_permission_reference: str = Field(min_length=8)
    epochs: int = Field(default=3, ge=1, le=20)
    learning_rate: float = Field(default=0.0002, gt=0, le=0.01)
    max_tokens: int = Field(default=1024, ge=32, le=8192)
    method: Literal["full", "lora", "qlora"] = "lora"
    memory_budget_gib: float = Field(default=6, gt=0)
    rank: int = Field(default=16, ge=2, le=128)
    seed: int = 42
    device: str = "cpu"
    precision: Literal["float32", "bfloat16"] = "float32"
    initial_adapter: Path | None = None
    gradient_checkpointing: bool = False

    @model_validator(mode="after")
    def compatible_stage(self):
        if self.initial_adapter and self.method != "full":
            raise ValueError("Adapter consolidation is an explicit full-weight stage")
        if self.method == "qlora" and not self.device.startswith("cuda"):
            raise ValueError("QLoRA requires a supported CUDA training GPU")
        if self.device == "cpu" and self.precision != "float32":
            raise ValueError("CPU training uses float32")
        return self


def verify_adapter(config):
    if not config.initial_adapter:
        return None
    directory = config.initial_adapter.resolve()
    report_path = directory / "distillation-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("mode") not in {"sequence_distillation_lora", "sequence_distillation_qlora"}:
        raise ValueError("Parent must be a recorded adapter training stage")
    if (report.get("student"), report.get("revision")) != (config.student, config.revision):
        raise ValueError("Adapter base model/revision does not match the full-weight stage")
    files = report.get("files", {})
    if not {"adapter_config.json", "adapter_model.safetensors"}.issubset(files):
        raise ValueError("Parent adapter is missing checksummed artifacts")
    for name, digest in files.items():
        if Path(name).name != name or (directory / name).resolve().parent != directory:
            raise ValueError("Invalid adapter artifact path")
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Parent adapter artifact checksum mismatch")
    return hashlib.sha256(report_path.read_bytes()).hexdigest()


def completion_loss(model, rows, device):
    import torch

    model.eval()
    total, tokens = 0.0, 0
    with torch.no_grad():
        for row in rows:
            count = sum(value != -100 for value in row["labels"][1:])
            inputs = {key: torch.tensor([value], device=device) for key, value in row.items()}
            total += float(model(**inputs).loss) * count
            tokens += count
    value = total / tokens
    if not torch.isfinite(torch.tensor(value)):
        raise ValueError("Evaluation loss is not finite")
    return value


def split_manifest(rows):
    return {
        kind: {
            hashlib.sha256(row[field].strip().encode()).hexdigest(): row["split"] for row in rows
        }
        for kind, field in [("groups", "patient_group"), ("prompts", "prompt")]
    }


def verify_stage_splits(config, rows):
    current = split_manifest(rows)
    if not config.initial_adapter:
        return current
    parent = json.loads(
        (config.initial_adapter / "distillation-report.json").read_text(encoding="utf-8")
    ).get("split_manifest")
    if not parent:
        raise ValueError(
            "Parent lacks split provenance; escalation cannot establish held-out integrity"
        )
    for kind, assignments in current.items():
        for identity, split in assignments.items():
            if identity in parent[kind] and parent[kind][identity] != split:
                raise ValueError("Case/group changes split across training stages")
    return {kind: {**parent[kind], **current[kind]} for kind in current}


def load_corpus(path):
    rows = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        raise ValueError("Teacher corpus is empty")
    identifiers, groups, prompts = set(), {}, {}
    for row in rows:
        required = {
            "case_id",
            "patient_group",
            "split",
            "prompt",
            "response",
            "teacher",
            "teacher_revision",
            "permission_reference",
            "privacy",
            "source_ids",
            "citations",
        }
        if not isinstance(row, dict) or not required.issubset(row):
            raise ValueError("Teacher case is missing provenance or split fields")
        if not all(
            isinstance(row[key], str) and row[key].strip()
            for key in required - {"source_ids", "citations"}
        ):
            raise ValueError("Case identity, content and provenance must be nonempty strings")
        if not all(
            isinstance(row[key], list)
            and all(isinstance(value, str) and value.strip() for value in row[key])
            for key in ["source_ids", "citations"]
        ):
            raise ValueError("Evidence identifiers must be lists of nonempty strings")
        if row["case_id"] in identifiers:
            raise ValueError("Duplicate teacher case ID")
        identifiers.add(row["case_id"])
        if row["split"] not in {"train", "validation", "test"}:
            raise ValueError("Use explicit train/validation/test splits")
        fingerprint = hashlib.sha256(row["prompt"].strip().encode()).hexdigest()
        if prompts.setdefault(fingerprint, row["split"]) != row["split"]:
            raise ValueError("Identical prompts overlap dataset splits")
        previous = groups.setdefault(row["patient_group"], row["split"])
        if previous != row["split"]:
            raise ValueError("Patient/case groups overlap dataset splits")
        if row["privacy"] not in {"synthetic", "approved_deidentified"}:
            raise ValueError("Only synthetic or explicitly cleared cases may enter distillation")
        if not all(
            isinstance(row[key], str) and row[key].strip()
            for key in ["prompt", "response", "teacher", "teacher_revision", "permission_reference"]
        ):
            raise ValueError("Teacher outputs and provenance must be nonempty strings")
        if not set(row["citations"]).issubset(set(row["source_ids"])):
            raise ValueError("Teacher output cites evidence not supplied with the case")
    if not all(
        any(row["split"] == split for row in rows) for split in ["train", "validation", "test"]
    ):
        raise ValueError("A separate training, validation and test set is required")
    return rows


def require_reviewed_corpus(rows):
    if any(row.get("review_status") != "approved" or not row.get("reviewer_id") for row in rows):
        raise ValueError("Training requires explicitly approved cases with reviewer identity")


def encode_case(tokenizer, row, max_tokens):
    prompt = tokenizer.apply_chat_template(
        [{"role": "user", "content": row["prompt"]}], tokenize=True, add_generation_prompt=True
    )
    completion = tokenizer.encode(row["response"], add_special_tokens=False)
    if tokenizer.eos_token_id is not None:
        completion += [tokenizer.eos_token_id]
    if len(prompt) + len(completion) > max_tokens:
        raise ValueError(
            "Case exceeds max_tokens; shorten it explicitly instead of truncating targets"
        )
    if not completion:
        raise ValueError("Teacher completion has no tokens")
    return {"input_ids": prompt + completion, "labels": [-100] * len(prompt) + completion}


def token_kl(student_logits, teacher_logits, labels, temperature=2.0):
    import torch.nn.functional as functional

    if student_logits.shape != teacher_logits.shape:
        raise ValueError(
            "Logit distillation requires identical tokenizer vocabulary and token alignment"
        )
    if temperature <= 0:
        raise ValueError("Temperature must be positive")
    mask = labels[:, 1:] != -100
    if not mask.any():
        raise ValueError("No completion tokens are available")
    student = functional.log_softmax(student_logits[:, :-1].float() / temperature, dim=-1)
    teacher = functional.softmax(teacher_logits[:, :-1].detach().float() / temperature, dim=-1)
    losses = functional.kl_div(student, teacher, reduction="none").sum(-1)
    return losses.masked_select(mask).mean() * temperature**2


def train_adapter(model, train, validation, output, epochs, rate, device, seed):
    import torch

    torch.manual_seed(seed)
    if not getattr(model, "is_loaded_in_4bit", False):
        model.to(device)
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad], lr=rate
    )
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    best, history = float("inf"), []
    generator = torch.Generator().manual_seed(seed)

    def batch(row):
        return {key: torch.tensor([value], device=device) for key, value in row.items()}

    def evaluate():
        return completion_loss(model, validation, device)

    initial = evaluate()
    if not torch.isfinite(torch.tensor(initial)):
        raise ValueError("Initial validation loss is not finite")
    best = initial
    model.save_pretrained(output, safe_serialization=True)
    for epoch in range(epochs):
        model.train()
        losses = []
        for index in torch.randperm(len(train), generator=generator).tolist():
            optimizer.zero_grad(set_to_none=True)
            loss = model(**batch(train[index])).loss
            if not torch.isfinite(loss):
                raise ValueError("Distillation produced a non-finite loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            losses.append(float(loss.detach()))
        validation_loss = evaluate()
        history.append(
            {
                "epoch": epoch + 1,
                "training_loss": sum(losses) / len(losses),
                "validation_loss": validation_loss,
            }
        )
        if validation_loss < best:
            model.save_pretrained(output, safe_serialization=True)
            best = validation_loss
    return {
        "initial_validation_loss": initial,
        "selected_validation_loss": best,
        "validation_improved": best < initial,
        "history": history,
    }


def run(config):
    import torch
    from transformers import (
        AutoConfig,
        AutoModelForCausalLM,
        AutoModelForImageTextToText,
        AutoTokenizer,
    )

    config = DistillationConfig.model_validate(config)
    if config.output.exists() and any(config.output.iterdir()):
        raise ValueError("Use a new output directory to preserve previous checkpoints")
    if config.device.startswith("cuda") and not torch.cuda.is_available():
        raise ValueError("CUDA was requested but is unavailable")
    if not Path(config.student).exists() and (
        len(config.revision) != 40
        or any(character not in "0123456789abcdef" for character in config.revision)
    ):
        raise ValueError("Remote model revisions must be immutable 40-character commit hashes")
    if config.precision == "bfloat16" and not torch.cuda.is_bf16_supported():
        raise ValueError("This CUDA device does not support the requested bfloat16 precision")
    if config.method == "qlora":
        import importlib.util

        if importlib.util.find_spec("bitsandbytes") is None:
            raise ValueError("QLoRA requires the optional bitsandbytes dependency on the GPU host")
    if "medgemma" in config.student.lower():
        # Conservative full-state allowance; adapter estimates exclude activations and adapters.
        bytes_per_parameter = (
            16
            if config.method == "full"
            else (0.5 if config.method == "qlora" else (4 if config.precision == "float32" else 2))
        )
        lower_bound = 4_000_000_000 * bytes_per_parameter / 1024**3
        if config.memory_budget_gib < lower_bound:
            raise ValueError(
                f"MedGemma {config.method} preflight requires at least {lower_bound:.1f} GiB "
                f"before activations/runtime overhead; budget is {config.memory_budget_gib} GiB. "
                "No weights downloaded."
            )
    parent_digest = verify_adapter(config)
    rows = load_corpus(config.corpus)
    require_reviewed_corpus(rows)
    stage_splits = verify_stage_splits(config, rows)
    tokenizer = AutoTokenizer.from_pretrained(
        config.student, revision=config.revision, trust_remote_code=False
    )
    encoded = {
        split: [
            encode_case(tokenizer, row, config.max_tokens) for row in rows if row["split"] == split
        ]
        for split in ["train", "validation", "test"]
    }
    model_config = AutoConfig.from_pretrained(
        config.student, revision=config.revision, trust_remote_code=False
    )
    loader = (
        AutoModelForImageTextToText if model_config.model_type == "gemma3" else AutoModelForCausalLM
    )
    torch.manual_seed(config.seed)
    load_options = {}
    if config.method == "qlora":
        from transformers import BitsAndBytesConfig

        load_options = {
            "quantization_config": BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=getattr(torch, config.precision),
            ),
            "device_map": {"": config.device},
        }
    model = loader.from_pretrained(
        config.student,
        revision=config.revision,
        trust_remote_code=False,
        torch_dtype=getattr(torch, config.precision),
        **load_options,
    )
    model.config.use_cache = False
    if config.method != "qlora":
        model.to(config.device)
    baseline_loss = completion_loss(model, encoded["test"], config.device)
    if config.initial_adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, config.initial_adapter).merge_and_unload(
            safe_merge=True
        )
    if config.method in {"lora", "qlora"}:
        from peft import LoraConfig, TaskType, get_peft_model

        if config.method == "qlora":
            from peft import prepare_model_for_kbit_training

            model = prepare_model_for_kbit_training(
                model, use_gradient_checkpointing=config.gradient_checkpointing
            )
        model = get_peft_model(
            model,
            LoraConfig(
                task_type=TaskType.CAUSAL_LM,
                r=config.rank,
                lora_alpha=config.rank * 2,
                lora_dropout=0.05,
                target_modules="all-linear",
            ),
        )
    else:
        for parameter in model.parameters():
            parameter.requires_grad_(True)
    if config.gradient_checkpointing and config.method != "qlora":
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()
    trainable_parameters = sum(p.numel() for p in model.parameters() if p.requires_grad)
    report = train_adapter(
        model,
        encoded["train"],
        encoded["validation"],
        config.output,
        config.epochs,
        config.learning_rate,
        config.device,
        config.seed,
    )
    if config.method in {"lora", "qlora"}:
        from peft import set_peft_model_state_dict
        from peft.utils.save_and_load import load_peft_weights

        set_peft_model_state_dict(
            model, load_peft_weights(str(config.output), device=config.device)
        )
    else:
        import gc

        del model
        gc.collect()
        if config.device.startswith("cuda"):
            torch.cuda.empty_cache()
        model = loader.from_pretrained(
            config.output, trust_remote_code=False, torch_dtype=getattr(torch, config.precision)
        ).to(config.device)
    report["held_out_test_completion_loss"] = completion_loss(model, encoded["test"], config.device)
    report["original_base_test_completion_loss"] = baseline_loss
    report["test_loss_delta_from_base"] = report["held_out_test_completion_loss"] - baseline_loss
    tokenizer.save_pretrained(config.output)
    report.update(
        mode="sequence_distillation_" + config.method,
        student=config.student,
        revision=config.revision,
        corpus_sha256=hashlib.sha256(config.corpus.read_bytes()).hexdigest(),
        split_counts={key: len(value) for key, value in encoded.items()},
        split_manifest=stage_splits,
        trainable_parameters=trainable_parameters,
        precision=config.precision,
        baseline_precision="nf4" if config.method == "qlora" else config.precision,
        parent_adapter_report_sha256=parent_digest,
        training_config=config.model_dump(mode="json"),
        clinical_status="not_validated",
        teacher_review="not_implied_by_training",
        model_permission_reference=config.model_permission_reference,
        test_set_used_for_selection=False,
    )
    report["files"] = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in config.output.iterdir()
        if path.is_file()
    }
    (config.output / "distillation-report.json").write_text(json.dumps(report, indent=2))
    return report
