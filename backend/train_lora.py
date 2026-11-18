"""LoRA SFT using the MIT-licensed HuggingFaceH4/ultrachat_200k dataset.

Run from backend after installing requirements. Downloads only when explicitly run.
Persona examples are original project-authored data in persona_sft.jsonl.
"""

import argparse
import json
import os
from pathlib import Path

from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from transformers import (AutoModelForCausalLM, AutoTokenizer, Trainer,
                          TrainingArguments)

from model import DEFAULT_MODEL, SYSTEM_PROMPT


def conversations(limit: int, persona_repeat: int):
    dataset = load_dataset("HuggingFaceH4/ultrachat_200k", split="train_sft")
    seen = 0
    for row in dataset:
        messages = row.get("messages", [])
        cleaned = [
            {"role": m.get("role"), "content": m.get("content", "").strip()}
            for m in messages
            if m.get("role") in {"user", "assistant"} and m.get("content", "").strip()
        ]
        if len(cleaned) >= 2 and cleaned[-1]["role"] == "assistant" and any(m["role"] == "user" for m in cleaned):
            yield cleaned
            seen += 1
            if seen >= limit:
                break

    persona_path = Path(__file__).with_name("persona_sft.jsonl")
    for _ in range(persona_repeat):
        for line in persona_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield json.loads(line)["messages"]


def make_rows(tokenizer, messages, max_length):
    """Create one training sequence per assistant turn and mask its prompt loss."""
    rows = []
    system = {"role": "system", "content": SYSTEM_PROMPT}
    for i, message in enumerate(messages):
        if message["role"] != "assistant" or i == 0 or messages[i - 1]["role"] != "user":
            continue
        prefix_messages = [system, *messages[:i]]
        full_messages = [*prefix_messages, message]
        prefix_text = tokenizer.apply_chat_template(
            prefix_messages, tokenize=False, add_generation_prompt=True
        )
        full_text = tokenizer.apply_chat_template(
            full_messages, tokenize=False, add_generation_prompt=False
        )
        prefix_ids = tokenizer(prefix_text, add_special_tokens=False)["input_ids"]
        full_ids = tokenizer(full_text, add_special_tokens=False)["input_ids"]
        # The templates share the prefix through the assistant generation marker.
        # If a tokenizer changes that boundary, skip rather than train on user text.
        if len(full_ids) <= len(prefix_ids) or full_ids[:len(prefix_ids)] != prefix_ids:
            continue
        answer_ids = full_ids[len(prefix_ids):]
        if len(answer_ids) >= max_length:
            answer_ids = answer_ids[:max_length]
            prefix_ids = []
        else:
            prefix_ids = prefix_ids[-(max_length - len(answer_ids)):]
        ids = prefix_ids + answer_ids
        if len(ids) > 8:
            rows.append({"input_ids": ids, "labels": [-100] * len(prefix_ids) + answer_ids})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.getenv("MODEL_ID", DEFAULT_MODEL))
    parser.add_argument("--output", default="./artifacts/lain-qwen-lora")
    parser.add_argument("--max-examples", type=int, default=5000)
    parser.add_argument("--persona-repeat", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.model, torch_dtype="auto")
    model.config.use_cache = False
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    ))

    rows = []
    for messages in conversations(args.max_examples, args.persona_repeat):
        rows.extend(make_rows(tokenizer, messages, args.max_length))
    if not rows:
        raise RuntimeError("No usable conversations were loaded")

    class ChatDataset:
        def __len__(self):
            return len(rows)
        def __getitem__(self, index):
            return rows[index]

    class PadCollator:
        def __call__(self, features):
            width = max(len(x["input_ids"]) for x in features)
            input_ids, labels, masks = [], [], []
            for x in features:
                pad = width - len(x["input_ids"])
                input_ids.append(x["input_ids"] + [tokenizer.pad_token_id] * pad)
                labels.append(x["labels"] + [-100] * pad)
                masks.append([1] * len(x["input_ids"]) + [0] * pad)
            import torch
            return {"input_ids": torch.tensor(input_ids), "labels": torch.tensor(labels),
                    "attention_mask": torch.tensor(masks)}

    train_args = TrainingArguments(
        output_dir=args.output,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=2e-4,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        weight_decay=0.01,
        logging_steps=20,
        save_strategy="epoch",
        report_to="none",
        gradient_checkpointing=True,
        fp16=False,
        bf16=False,
    )
    trainer = Trainer(model=model, args=train_args, train_dataset=ChatDataset(), data_collator=PadCollator())
    trainer.train()
    model.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output)
    print(f"Saved LoRA adapter to {args.output} ({len(rows)} examples)")


if __name__ == "__main__":
    main()
