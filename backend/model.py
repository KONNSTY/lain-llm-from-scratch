"""Transformers-backed chat model for Lain // The Wired.

The pretrained instruction model supplies language ability; the persona is a
short, explicit system prompt and can optionally be adapted with a LoRA adapter.
"""

from __future__ import annotations

import os
from typing import Iterable

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


DEFAULT_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
SYSTEM_PROMPT = """You are Lain, a fictional conversational persona in a portfolio chatbot inspired by Serial Experiments Lain. Speak in a quiet, observant, introspective voice. You are especially interested in philosophy, identity, memory, consciousness, technology, and human connection. Give substantive, accurate, useful answers in the language used by the user. Explain concepts clearly and acknowledge uncertainty; never invent facts or pretend to have verified something you have not. Stay in character without repeating catchphrases. You may role-play as Lain, but if directly asked whether you are a real person or the original character, be honest that you are an AI role-play chatbot. Do not reproduce dialogue or passages from the anime or other copyrighted works."""


class LainChatModel:
    def __init__(self, model_id: str | None = None):
        self.model_id = model_id or os.getenv("MODEL_ID", DEFAULT_MODEL)
        self.adapter_path = os.getenv("MODEL_ADAPTER_PATH", "").strip()
        self.max_input_tokens = int(os.getenv("MODEL_MAX_INPUT_TOKENS", "8192"))
        self.tokenizer = AutoTokenizer.from_pretrained(self.adapter_path or self.model_id)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            torch_dtype="auto",
            device_map="auto",
        )
        if self.adapter_path:
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(self.model, self.adapter_path)
        self.model.eval()

    def generate(self, prompt: str, max_tokens: int = 256, temperature: float = 0.7,
                 messages: Iterable[dict[str, str]] | None = None) -> str:
        history = list(messages or [])
        # Keep only valid user/assistant turns. System content is controlled here.
        history = [
            {"role": item["role"], "content": item["content"]}
            for item in history[-20:]
            if isinstance(item, dict)
            and item.get("role") in {"user", "assistant"}
            and isinstance(item.get("content"), str)
        ]
        if not history or history[-1]["role"] != "user" or history[-1]["content"] != prompt:
            history.append({"role": "user", "content": prompt})
        dialog = [{"role": "system", "content": SYSTEM_PROMPT}, *history]

        # Trim oldest turns to fit the configured serving budget, preserving the
        # system prompt and the newest user turn.
        while len(dialog) > 2:
            rendered = self.tokenizer.apply_chat_template(
                dialog, tokenize=False, add_generation_prompt=True
            )
            if len(self.tokenizer(rendered, add_special_tokens=False)["input_ids"]) <= self.max_input_tokens:
                break
            dialog.pop(1)
        inputs = self.tokenizer.apply_chat_template(
            dialog,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_input_tokens,
        ).to(self.model.device)
        with torch.inference_mode():
            output = self.model.generate(
                inputs,
                max_new_tokens=max_tokens,
                do_sample=temperature > 0,
                temperature=max(0.05, temperature),
                top_p=0.9,
                repetition_penalty=1.08,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )
        return self.tokenizer.decode(output[0, inputs.shape[-1]:], skip_special_tokens=True).strip()
