"""Exercise actual transformer/LoRA distillation on synthetic tokens, not clinical cases."""

import json
from pathlib import Path

import torch
from peft import LoraConfig, TaskType, get_peft_model
from transformers import GPT2Config, GPT2LMHeadModel

from medflock.distillation import token_kl, train_adapter


def main():
    torch.set_num_threads(1)
    torch.manual_seed(42)
    output = Path("artifacts/llm-smoke")
    teacher = GPT2LMHeadModel(
        GPT2Config(
            vocab_size=24,
            n_positions=32,
            n_embd=32,
            n_layer=2,
            n_head=2,
            bos_token_id=1,
            eos_token_id=2,
        )
    )
    corpus = [
        {"input_ids": [1, 3 + index, 4, 5, 6, 2], "labels": [-100, -100, -100, 5, 6, 2]}
        for index in range(12)
    ]
    teacher_optimizer = torch.optim.AdamW(teacher.parameters(), lr=0.005)
    for _ in range(20):
        for row in corpus[:8]:
            teacher_optimizer.zero_grad()
            teacher(**{key: torch.tensor([value]) for key, value in row.items()}).loss.backward()
            teacher_optimizer.step()
    teacher.eval()
    for parameter in teacher.parameters():
        parameter.requires_grad = False
    student = GPT2LMHeadModel(
        GPT2Config(
            vocab_size=24,
            n_positions=32,
            n_embd=32,
            n_layer=1,
            n_head=2,
            bos_token_id=1,
            eos_token_id=2,
        )
    )
    student = get_peft_model(
        student,
        LoraConfig(
            task_type=TaskType.CAUSAL_LM, r=4, lora_alpha=8, target_modules=["c_attn", "c_proj"]
        ),
    )
    optimizer = torch.optim.AdamW([p for p in student.parameters() if p.requires_grad], lr=0.01)

    def distance(rows):
        student.eval()
        with torch.no_grad():
            return sum(
                float(
                    token_kl(
                        student(input_ids=torch.tensor([row["input_ids"]])).logits,
                        teacher(input_ids=torch.tensor([row["input_ids"]])).logits,
                        torch.tensor([row["labels"]]),
                    )
                )
                for row in rows
            ) / len(rows)

    before = distance(corpus[8:10])
    for _ in range(30):
        student.train()
        for row in corpus[:8]:
            inputs, labels = torch.tensor([row["input_ids"]]), torch.tensor([row["labels"]])
            with torch.no_grad():
                teacher_logits = teacher(input_ids=inputs).logits
            optimizer.zero_grad()
            loss = token_kl(student(input_ids=inputs).logits, teacher_logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(student.parameters(), 1.0)
            optimizer.step()
    after = distance(corpus[8:10])
    assert after < before, "Synthetic distillation did not reduce held-out teacher divergence"
    report = train_adapter(student, corpus[:8], corpus[8:10], output, 2, 0.001, "cpu", 42)
    report.update(
        scope="synthetic_transformer_integration_only",
        teacher_parameters=sum(p.numel() for p in teacher.parameters()),
        trainable_student_parameters=sum(
            p.numel() for p in student.parameters() if p.requires_grad
        ),
        initial_validation_kl=before,
        final_validation_kl=after,
        test_kl=distance(corpus[10:]),
        clinical_validation=False,
        pretrained_medical_model_used=False,
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "smoke-report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
